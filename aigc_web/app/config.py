import os
from pathlib import Path

# BASE_DIR = aigc_web/，PROJECT_ROOT = web/（包含 aigc_web、scripts 的项目根目录）
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

DB_PATH = Path(os.getenv("AIGC_DB_PATH") or (BASE_DIR / "aigc_web.db"))
SECRET_KEY = os.getenv("AIGC_WEB_SECRET", "change-this-in-production")
TOKEN_EXPIRE_HOURS = int(os.getenv("AIGC_TOKEN_EXPIRE_HOURS", "24"))


def resolve_project_path(env_value: str, default_relative: str) -> str:
    """把模型/脚本路径统一解析为绝对路径。

    规则：环境变量为空时用 default_relative；无论来自环境变量还是默认值，
    相对路径一律以项目根目录（web/）为基准，避免依赖启动时的工作目录。
    """
    raw = (env_value or "").strip() or default_relative
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


# 词级模型权重（默认放在项目根目录下，可用 WORD_MODEL_PATH 覆盖）
WORD_MODEL_PATH = resolve_project_path(
    os.getenv("WORD_MODEL_PATH", ""),
    "deberta_CRF(new)_best.pt",
)
WORD_MODEL_NAME = os.getenv("WORD_MODEL_NAME", "microsoft/deberta-v3-base")

# 词级边界外部推理脚本
WORD_BOUNDARY_BACKEND_SCRIPT = resolve_project_path(
    os.getenv("WORD_BOUNDARY_BACKEND_SCRIPT", ""),
    "scripts/deberta_CRF(new)_single_text.py",
)

# 句子级外部推理脚本
SENTENCE_BACKEND_SCRIPT = resolve_project_path(
    os.getenv("SENTENCE_BACKEND_SCRIPT", ""),
    "scripts/test_single_text.py",
)

# 句子级脚本依赖的两个模型目录：两者都存在时才认为外部后端可用
GPT2_MODEL_DIR = resolve_project_path(
    os.getenv("AIGC_GPT2_MODEL_DIR", ""),
    "scripts/gpt2-xl",
)
SENTENCE_HEAD_DIR = resolve_project_path(
    os.getenv("AIGC_SENTENCE_HEAD_DIR", ""),
    "scripts/windows_log/windows_webuse",
)
