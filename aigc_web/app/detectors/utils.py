"""文本切句 / 分词工具（中英文混排）。

设计要点：
- 切句返回的每一句都是原文的子串（调用方通过 ``text.find`` 定位），
  因此这里只做裁剪、不改写字符。
- 中文没有空格，不能再用 ``\\s+`` 当句界。中文标点（。！？；…）后直接成句；
  英文句号等仍要求后面是空白或结尾，避免切开 ``3.14`` / ``e.g.``。
- 分词优先使用 jieba（如果环境里装了）；未安装时退化为「中文按字、英文按词、
  标点按串」，保证不引入硬依赖也能得到字符级 span。输出结构保持
  ``{index, token, start, end}``，上层逻辑无需改动。
"""

import re
from typing import Any

try:  # 可选依赖：装了 jieba 会得到更自然的词级切分
    import jieba
except Exception:  # pragma: no cover - 环境未安装时走退化实现
    jieba = None


_CJK_RANGE = "\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"

# 中文标点直接断句；英文标点要求后接空白或到达结尾
# 注意：分号（；/;）是句内并列，不作为句界
_SENT_BOUNDARY_RE = re.compile(
    r"[。！？…]+"
    r"|[.!?]+(?=\s|$)"
    r"|\n+"
)

# 句末可能跟着引号/括号，应当归入当前句而不是下一句
_CLOSERS = "”’」』）)》】»\"'"

# 分词退化实现：英文词/数字 → 单个汉字 → 标点串
_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]+(?:[’'\-_][A-Za-z0-9]+)*"
    rf"|[{_CJK_RANGE}]"
    rf"|[^{_CJK_RANGE}A-Za-z0-9\s]+"
)


def split_sentences(text: str) -> list[str]:
    """把文本切成句子，返回值均为原文本的子串（去首尾空白）。"""
    text = (text or "").strip()
    if not text:
        return []

    sentences: list[str] = []
    start = 0
    for match in _SENT_BOUNDARY_RE.finditer(text):
        end = match.end()
        while end < len(text) and text[end] in _CLOSERS:
            end += 1
        chunk = text[start:end].strip()
        if chunk:
            sentences.append(chunk)
        start = end

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)

    return sentences or [text]


def tokenize_with_spans(text: str) -> list[dict[str, Any]]:
    """切分为带字符区间的 token 列表。

    返回的 token 覆盖所有非空白字符（空白由前端从原文补齐），
    因此可以直接用 ``start/end`` 在原文上还原高亮。
    """
    text = text or ""
    raw_tokens: list[tuple[str, int, int]] = []

    if jieba is not None:
        for word, start, end in jieba.tokenize(text):
            if word.strip():
                raw_tokens.append((word, start, end))
    else:
        for match in _TOKEN_RE.finditer(text):
            raw_tokens.append((match.group(0), match.start(), match.end()))

    return [
        {"index": idx, "token": token, "start": start, "end": end}
        for idx, (token, start, end) in enumerate(raw_tokens)
    ]
