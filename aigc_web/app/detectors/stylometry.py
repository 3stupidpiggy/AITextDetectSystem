"""句子级风格特征打分。

根据衔接词、书面语词、具体信息与人称等文体特征，估计句子由 AI 生成的概率。
输出结构与 SentenceLevelDetector 一致：包含 label、confidence 与 ai_ratio（0~1）。
"""

from __future__ import annotations

import math
import re
from typing import Any

from .utils import split_sentences

_DISCOURSE_WORDS = (
    "综上所述", "总而言之", "总的来说", "由此可见", "简而言之", "具体而言",
    "一方面", "另一方面", "与此同时", "值得注意", "唯有如此",
    "首先", "其次", "再次", "最后", "此外", "总之", "综上",
    "因此", "从而", "不仅", "而且", "然而", "换言之",
    "furthermore", "moreover", "in addition", "in conclusion",
    "consequently", "therefore", "on the one hand", "on the other hand",
    "importantly", "notably", "in summary", "in other words",
)

_GENERIC_WORDS = (
    "前所未有", "不可忽视", "不可或缺", "至关重要", "深刻", "深远", "显著",
    "极大", "巨大", "充分", "全面", "有效", "日益",
    "构建", "赋能", "助力", "推动", "实现", "挑战", "机遇", "变革",
    "转型", "生态", "数字化", "可持续",
    "crucial", "vital", "comprehensive", "robust", "leverage", "delve",
    "landscape", "realm", "pivotal", "foster", "navigate", "underscore",
    "paradigm", "unparalleled",
)

_PERSON_WORDS = ("我们", "我", "咱", r"I\b", r"my\b", r"we\b", r"our\b", r"me\b")

_SPECIFIC_RE = re.compile(r"\d|[“”「」『』]|——|…")


def _build_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    # 长词优先，避免「综上所述」被「综上」重复计数
    ordered = sorted(set(words), key=len, reverse=True)
    return re.compile("|".join(ordered), re.IGNORECASE)


_DISCOURSE_RE = _build_pattern(_DISCOURSE_WORDS)
_GENERIC_RE = _build_pattern(_GENERIC_WORDS)
_PERSON_RE = _build_pattern(_PERSON_WORDS)


def _rate(pattern: re.Pattern[str], text: str) -> float:
    """每 100 字的命中次数（+20 平滑，避免短句过度敏感）。"""
    return len(pattern.findall(text)) * 100.0 / (len(text) + 20.0)


def score_sentence(sentence: str) -> float:
    """返回该句为 AI 生成的概率（0~1）。"""
    text = (sentence or "").strip()
    if not text:
        return 0.5

    discourse = min(1.0, _rate(_DISCOURSE_RE, text) / 1.5)
    generic = min(1.0, _rate(_GENERIC_RE, text) / 1.5)
    person = min(1.0, _rate(_PERSON_RE, text) / 1.5)
    specific = min(1.0, _rate(_SPECIFIC_RE, text) / 2.0)

    raw = (
        2.0 * discourse
        + 1.2 * generic
        - 1.6 * person
        - 1.9 * specific
        - 0.55
    )
    return 1.0 / (1.0 + math.exp(-1.7 * raw))


def detect(text: str) -> dict[str, Any]:
    """对文本做句子级判定，返回与 SentenceLevelDetector 兼容的结构。"""
    sentences = split_sentences(text)
    rows: list[dict[str, Any]] = []
    first_ai = None

    for index, sentence in enumerate(sentences):
        score = score_sentence(sentence)
        label = "AIGT" if score >= 0.5 else "HWT"
        confidence = max(score, 1.0 - score)
        if label == "AIGT" and first_ai is None:
            first_ai = index
        rows.append(
            {
                "index": index,
                "text": sentence,
                "label": label,
                "confidence": round(float(confidence), 4),
                "ai_ratio": round(float(score), 4),
            }
        )

    switch_index = first_ai if first_ai is not None else 0

    return {
        "sentences": rows,
        "switch_sentence_index": switch_index,
        "model_used": "stylometry",
    }


# ---------- 词级片段标注 ----------

_CLAUSE_SEPARATORS = set("，,；;—")
_SENTENCE_SEPARATORS = set("。！？.!?…\n")


def _expand_region_start(text: str, position: int, limit: int = 30) -> int:
    """把片段起点向前扩到最近的逗号/分号/破折号，最多回退 limit 个字符。"""
    index = position
    while index > 0 and position - index <= limit:
        if text[index - 1] in _CLAUSE_SEPARATORS or text[index - 1] in _SENTENCE_SEPARATORS:
            return index
        index -= 1
    return max(0, position - 6)


def _expand_region_end(text: str, position: int, limit: int = 60) -> int:
    """把片段终点向后扩到最近的句末标点，最多前进 limit 个字符。"""
    index = position
    while index < len(text) and index - position <= limit:
        if text[index] in _SENTENCE_SEPARATORS:
            return index + 1
        index += 1
    return min(len(text), position + 6)


def _ai_regions(text: str, gap: int = 100, min_marks: int = 2) -> list[tuple[int, int]]:
    """把距离较近的 AI 特征词合并成片段，至少包含 min_marks 个特征词。"""
    marks: list[tuple[int, int]] = []
    for pattern in (_DISCOURSE_RE, _GENERIC_RE):
        for match in pattern.finditer(text):
            marks.append((match.start(), match.end()))
    marks.sort()

    clusters: list[list[int]] = []
    for start, end in marks:
        if clusters and start - clusters[-1][1] <= gap:
            clusters[-1][1] = max(clusters[-1][1], end)
            clusters[-1][2] += 1
        else:
            clusters.append([start, end, 1])

    regions: list[tuple[int, int]] = []
    for start, end, count in clusters:
        if count < min_marks:
            continue
        regions.append((_expand_region_start(text, start), _expand_region_end(text, end)))
    return regions


def label_tokens(text: str, tokens: list[dict[str, Any]]) -> list[int]:
    """按 AI 特征词片段给每个 token 打标签，1 表示 AI 片段内。"""
    regions = _ai_regions(text)
    if not regions:
        return [0] * len(tokens)

    labels: list[int] = []
    for token in tokens:
        middle = (token["start"] + token["end"]) / 2.0
        labels.append(1 if any(start <= middle <= end for start, end in regions) else 0)
    return labels
