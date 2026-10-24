"""启动脚本：python run.py 127.0.0.1:8000

参数直接写「地址:端口」，也可以只写端口；无需再指定 --app-dir。

用法：
    python run.py                       # 默认 127.0.0.1:8000
    python run.py 127.0.0.1:8000        # 指定地址和端口
    python run.py 127.0.0.1:8010        # 换端口
    python run.py 8010                  # 只写端口（地址默认 127.0.0.1）
    python run.py 0.0.0.0:8000          # 局域网演示
    python run.py 127.0.0.1:8010 --reload   # 开发时自动重载
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
APP_DIR = PROJECT_ROOT / "aigc_web"
DEFAULT_TARGET = "127.0.0.1:8000"


def parse_target(value: str) -> tuple[str, int]:
    """把 '127.0.0.1:8000' / '8000' / '[::1]:8000' 解析成 (host, port)。"""
    text = (value or "").strip()
    if not text:
        return "127.0.0.1", 8000

    if text.isdigit():
        return "127.0.0.1", int(text)

    if text.startswith("[") and "]:" in text:
        host, _, port = text[1:].partition("]:")
        if host and port.isdigit():
            return host, int(port)

    host, _, port = text.rpartition(":")
    if host and port.isdigit():
        return host, int(port)

    raise ValueError(f"无法识别的地址：{value}（示例：127.0.0.1:8000 或 8000）")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run.py", description="启动 AIGC 文本检测系统")
    parser.add_argument(
        "target",
        nargs="?",
        default=DEFAULT_TARGET,
        help="监听地址，如 127.0.0.1:8000；只写 8000 则地址默认 127.0.0.1",
    )
    parser.add_argument("--host", default=None, help="覆盖监听地址")
    parser.add_argument("--port", dest="port_option", type=int, default=None, help="覆盖监听端口")
    parser.add_argument("--reload", action="store_true", help="代码变更后自动重载")
    args = parser.parse_args(argv)

    try:
        host, port = parse_target(args.target)
    except ValueError as exc:
        parser.error(str(exc))

    if args.host:
        host = args.host
    if args.port_option is not None:
        port = args.port_option
    if not 1 <= port <= 65535:
        parser.error("端口需要在 1~65535 之间")

    args.host = host
    args.port = port
    return args


def main() -> None:
    args = parse_args(sys.argv[1:])

    try:
        import uvicorn
    except ImportError:
        print("未找到 uvicorn，请先安装：python -m pip install fastapi \"uvicorn[standard]\" python-multipart")
        raise SystemExit(1)

    if not (APP_DIR / "app" / "main.py").is_file():
        print(f"未找到应用入口：{APP_DIR / 'app' / 'main.py'}")
        raise SystemExit(1)

    # 启动横幅按演示需要关闭；需要时取消下面两行注释即可恢复
    # display_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    # print(f"AIGC 文本检测系统：{args.host}:{args.port}")
    # print(f"浏览器访问：http://{display_host}:{args.port}")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(APP_DIR),
    )


if __name__ == "__main__":
    main()
