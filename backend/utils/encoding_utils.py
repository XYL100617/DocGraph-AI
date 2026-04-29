from pathlib import Path


def read_text_auto(file_path: str) -> str:
    """
    尝试按多种编码读取文本文件，顺序：utf-8, utf-8-sig, utf-16, utf-16-le, utf-16-be, gbk。
    如果全部失败，抛出 ValueError。
    """
    encodings = [
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "gbk",
    ]

    p = Path(file_path)
    if not p.exists():
        raise ValueError(f"file not found: {file_path}")

    last_exc = None
    for enc in encodings:
        try:
            return p.read_text(encoding=enc)
        except Exception as e:
            last_exc = e

    raise ValueError(f"无法解析文件编码: {file_path}. 尝试的编码: {encodings}. 最后错误: {last_exc}")
# backend/utils/encoding_utils.py

from pathlib import Path

def read_text_auto(file_path: str) -> str:
    """
    自动识别编码读取文本（UTF-8 / UTF-16 / GBK）
    """

    encodings = [
        "utf-8",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "gbk"
    ]

    for enc in encodings:
        try:
            return Path(file_path).read_text(encoding=enc)
        except Exception:
            continue

    raise ValueError(f"无法解析文件编码: {file_path}")