from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import GPT2_MODEL_DIR, SENTENCE_BACKEND_SCRIPT, SENTENCE_HEAD_DIR
from .stylometry import detect as style_detect
from .utils import split_sentences

logger = logging.getLogger(__name__)


@dataclass
class SentencePredictResult:
    sentences: list[dict[str, Any]]
    switch_sentence_index: int
    model_used: str


class SentenceLevelDetector:
    """
    句子级检测。

    优先调用外部后端脚本 scripts/test_single_text.py；
    不可用时使用内置风格特征打分（stylometry）。
    """

    def __init__(self) -> None:
        script = str(SENTENCE_BACKEND_SCRIPT or "").strip()
        self._external_script = script
        self._external_ready = bool(
            script
            and Path(script).is_file()
            and Path(GPT2_MODEL_DIR).exists()
            and Path(SENTENCE_HEAD_DIR).exists()
        )
        self._external_disabled = False
        if not self._external_ready:
            logger.debug("Sentence backend not configured: %s / %s", GPT2_MODEL_DIR, SENTENCE_HEAD_DIR)

    def _compute_switch_idx(self, sentence_rows: list[dict[str, Any]]) -> int:
        for row in sentence_rows:
            if row.get("label") == "AIGT":
                return int(row.get("index", 0))
        return 0

    def _call_external_backend(self, text: str) -> SentencePredictResult | None:
        if not self._external_ready or self._external_disabled:
            return None

        # External script is expected to support a lightweight single-text mode.
        cmd = [
            sys.executable,
            self._external_script,
            "--single_text",
            text,
            "--output_json",
        ]

        try:
            completed = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=45,
            )
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            if not lines:
                return None
            payload = json.loads(lines[-1])
            rows_raw = payload.get("sentences", [])
            rows: list[dict[str, Any]] = []
            for idx, item in enumerate(rows_raw):
                label = str(item.get("label", "HWT")).upper()
                rows.append(
                    {
                        "index": idx,
                        "text": str(item.get("text", "")),
                        "label": "AIGT" if label == "AIGT" else "HWT",
                        "confidence": round(float(item.get("confidence", 0.5)), 4),
                        "ai_ratio": round(float(item.get("ai_ratio", 1.0 if label == "AIGT" else 0.0)), 4),
                    }
                )

            if not rows:
                return None

            return SentencePredictResult(
                sentences=rows,
                switch_sentence_index=int(payload.get("switch_sentence_index", self._compute_switch_idx(rows))),
                model_used="sentence-model",
            )
        except Exception as exc:
            # 一次性失败就停用，避免每次请求都付一次子进程启动的成本
            self._external_disabled = True
            logger.debug("Sentence backend failed: %s", exc)
            return None

    def _aggregate_from_words(self, text: str, words: list[dict[str, Any]]) -> SentencePredictResult:
        sents = split_sentences(text)
        if not sents:
            return SentencePredictResult(sentences=[], switch_sentence_index=0, model_used="aggregated-word-signal")

        cursor = 0
        sentence_rows: list[dict[str, Any]] = []
        for idx, sent in enumerate(sents):
            start = text.find(sent, cursor)
            if start < 0:
                start = cursor
            end = start + len(sent)
            cursor = end

            within = [w for w in words if w["start"] >= start and w["end"] <= end]
            if not within:
                ai_ratio = 0.0
                confidence = 0.5
            else:
                ai_count = sum(1 for w in within if w["label_id"] == 1)
                ai_ratio = ai_count / len(within)
                confidence = max(0.5, min(0.99, 0.5 + abs(ai_ratio - 0.5)))

            label = "AIGT" if ai_ratio >= 0.5 else "HWT"
            sentence_rows.append(
                {
                    "index": idx,
                    "text": sent,
                    "label": label,
                    "confidence": round(float(confidence), 4),
                    "ai_ratio": round(float(ai_ratio), 4),
                }
            )

        switch_idx = self._compute_switch_idx(sentence_rows)

        return SentencePredictResult(
            sentences=sentence_rows,
            switch_sentence_index=switch_idx,
            model_used="aggregated-word-signal",
        )

    def _style(self, text: str) -> SentencePredictResult:
        payload = style_detect(text)
        return SentencePredictResult(
            sentences=payload["sentences"],
            switch_sentence_index=int(payload["switch_sentence_index"]),
            model_used=str(payload["model_used"]),
        )

    def predict(self, text: str, words: list[dict[str, Any]] | None = None) -> SentencePredictResult:
        external = self._call_external_backend(text)
        if external is not None:
            return external

        if words is not None:
            return self._aggregate_from_words(text, words)

        return self._style(text)
