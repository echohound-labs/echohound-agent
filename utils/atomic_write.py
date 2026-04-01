"""
utils/atomic_write.py — Crash-safe file writes
Write to temp file then os.replace() — atomic on POSIX.
Prevents partial writes from corrupting memory files on crash.
"""
import os
import tempfile


def atomic_write(path: str, content: str, encoding: str = "utf-8"):
    """Write content to path atomically. Never leaves a partial file."""
    dir_ = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(dir_, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=dir_, delete=False, suffix=".tmp", encoding=encoding
    ) as f:
        f.write(content)
        tmp = f.name
    os.replace(tmp, path)  # atomic on POSIX, best-effort on Windows
