from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..config import WORD_MODEL_NAME, WORD_MODEL_PATH
from .stylometry import label_tokens
from .utils import tokenize_with_spans

logger = logging.getLogger(__name__)


@dataclass
class WordPredictResult:
    words: list[dict[str, Any]]
    switch_word_index: int
    model_used: str


class WordLevelDetector:
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self.device = None
        self.ready = False
        self.max_len = 512

        try:
            import torch

            # 关闭 transformers 导入阶段的版本提示（torch 2.0 会被提示需 >= 2.1），不影响功能
            logging.getLogger("transformers.utils.import_utils").setLevel(logging.ERROR)
            from transformers import AutoTokenizer

            from .word_model_runtime import DeBERTaCRFTagger, infer_document_with_sliding_windows

            self._torch = torch
            self._infer_fn = infer_document_with_sliding_windows
            self.tokenizer = AutoTokenizer.from_pretrained(WORD_MODEL_NAME)
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = DeBERTaCRFTagger(WORD_MODEL_NAME, 2).to(self.device)
            ckpt = torch.load(WORD_MODEL_PATH, map_location=self.device, weights_only=False)
            state = ckpt.get("model_state_dict", ckpt)
            self.model.load_state_dict(state)
            self.model.eval()
            self.ready = True
            logger.info("Word model loaded from %s", WORD_MODEL_PATH)
        except Exception as exc:
            logger.debug("Word-level model not loaded: %s", exc)

    def predict(self, text: str) -> WordPredictResult:
        if not self.ready:
            return WordPredictResult(words=[], switch_word_index=0, model_used="unavailable")

        tokens = tokenize_with_spans(text)
        words = [t["token"] for t in tokens]
        if not words:
            return WordPredictResult(words=[], switch_word_index=0, model_used="deberta-crf")

        pred_labels, boundary, vote_counts = self._infer_fn(
            self.model,
            words,
            self.tokenizer,
            self.max_len,
            self.device,
            base_window=512,
            base_stride=384,
            short_window_cap=256,
        )

        rows = []
        for i, token_item in enumerate(tokens):
            vote0 = int(vote_counts[i, 0]) if i < vote_counts.shape[0] else 0
            vote1 = int(vote_counts[i, 1]) if i < vote_counts.shape[0] else 0
            total = max(1, vote0 + vote1)
            conf = max(vote0, vote1) / total
            label_id = int(pred_labels[i]) if i < len(pred_labels) else 0
            rows.append(
                {
                    **token_item,
                    "label": "AIGT" if label_id == 1 else "HWT",
                    "label_id": label_id,
                    "confidence": round(float(conf), 4),
                }
            )

        return WordPredictResult(words=rows, switch_word_index=int(boundary), model_used="deberta-crf")

    def _sentence_spans(self, text: str, sentence_rows: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        cursor = 0
        for row in sentence_rows:
            sent = str(row.get("text", "")).strip()
            if not sent:
                continue
            start = text.find(sent, cursor)
            if start < 0:
                start = cursor
            end = start + len(sent)
            cursor = end
            label = "AIGT" if str(row.get("label", "")).upper() == "AIGT" else "HWT"
            spans.append((start, end, label))
        return spans

    def _compute_first_switch_word_index(self, labels: list[int]) -> int:
        if not labels:
            return 0
        for idx in range(1, len(labels)):
            if labels[idx] != labels[idx - 1]:
                return idx - 1
        return 0

    def _predict_spans(self, text: str, tokens: list[dict[str, Any]]) -> WordPredictResult:
        """无词级模型时，按 AI 特征词片段做 token 级标注。"""
        labels = label_tokens(text, tokens)
        rows: list[dict[str, Any]] = []
        for i, tok in enumerate(tokens):
            lid = int(labels[i])
            rows.append(
                {
                    **tok,
                    "label": "AIGT" if lid == 1 else "HWT",
                    "label_id": lid,
                    "confidence": 0.86 if lid == 1 else 0.72,
                }
            )
        switch_idx = self._compute_first_switch_word_index(labels)
        return WordPredictResult(words=rows, switch_word_index=switch_idx, model_used="span-aligned")

    def predict_with_sentence_switches(self, text: str, sentence_rows: list[dict[str, Any]]) -> WordPredictResult:
        tokens = tokenize_with_spans(text)
        if not tokens:
            return WordPredictResult(words=[], switch_word_index=0, model_used="switch-aware-empty")

        if not self.ready:
            return self._predict_spans(text, tokens)

        if not sentence_rows:
            return self.predict(text)

        spans = self._sentence_spans(text, sentence_rows)
        if not spans:
            return self.predict(text)

        token_labels = [0 for _ in tokens]
        token_conf = [0.65 for _ in tokens]

        # Step 1: initialize token labels by sentence labels.
        sentence_token_indices: list[list[int]] = []
        for start, end, sent_label in spans:
            idxs = [
                i
                for i, tok in enumerate(tokens)
                if tok["start"] >= start and tok["end"] <= end
            ]
            sentence_token_indices.append(idxs)
            label_id = 1 if sent_label == "AIGT" else 0
            for i in idxs:
                token_labels[i] = label_id
                token_conf[i] = 0.7

        # Step 2~4: 逐个人机切换点做词级细化。
        for i in range(len(spans) - 1):
            left_label = spans[i][2]
            right_label = spans[i + 1][2]
            if left_label == right_label:
                continue

            left_idxs = sentence_token_indices[i]
            right_idxs = sentence_token_indices[i + 1]
            combined_idxs = left_idxs + right_idxs
            if not combined_idxs:
                continue

            left_text = text[spans[i][0] : spans[i][1]].strip()
            right_text = text[spans[i + 1][0] : spans[i + 1][1]].strip()
            local_text = f"{left_text} {right_text}".strip()
            if not local_text:
                continue
            local_res = self.predict(local_text)
            local_boundary = int(local_res.switch_word_index)
            local_boundary = max(0, min(local_boundary, len(combined_idxs) - 1))
            boundary_global = combined_idxs[local_boundary]
            boundary_conf = 0.88

            left_id = 1 if left_label == "AIGT" else 0
            right_id = 1 if right_label == "AIGT" else 0
            for gi in combined_idxs:
                if gi <= boundary_global:
                    token_labels[gi] = left_id
                else:
                    token_labels[gi] = right_id
                token_conf[gi] = boundary_conf

        rows: list[dict[str, Any]] = []
        for i, tok in enumerate(tokens):
            lid = int(token_labels[i])
            rows.append(
                {
                    **tok,
                    "label": "AIGT" if lid == 1 else "HWT",
                    "label_id": lid,
                    "confidence": round(float(token_conf[i]), 4),
                }
            )

        switch_idx = self._compute_first_switch_word_index(token_labels)
        return WordPredictResult(
            words=rows,
            switch_word_index=switch_idx,
            model_used="switch-aware-deberta-crf",
        )
