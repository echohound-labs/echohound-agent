"""
Tool: file_ops
==============
Safe file read/write/list operations.
Sandboxed to the agent's working directory by default.
"""

import os
import json
from pathlib import Path
from typing import Optional, Union

# Safety: restrict file ops to this directory tree by default
SANDBOX_ROOT = Path(os.getcwd())


def _safe_path(path: str) -> Path:
    """Resolve path and ensure it stays within sandbox."""
    resolved = (SANDBOX_ROOT / path).resolve()
    if not str(resolved).startswith(str(SANDBOX_ROOT)):
        raise PermissionError(f"Path '{path}' is outside the sandbox root.")
    return resolved


def file_read(path: str, offset: int = 1, limit: int = 200) -> dict:
    """
    Read a file. Returns lines offset..offset+limit.

    Args:
        path:   Relative path to file
        offset: Line number to start from (1-indexed)
        limit:  Max lines to return
    """
    try:
        p = _safe_path(path)
        if not p.exists():
            return {"error": f"File not found: {path}"}
        lines = p.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        chunk = lines[offset - 1: offset - 1 + limit]
        return {
            "path": path,
            "lines": chunk,
            "total_lines": total,
            "offset": offset,
            "returned": len(chunk),
        }
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def file_write(path: str, content: str, overwrite: bool = True) -> dict:
    """
    Write content to a file. Creates parent directories as needed.

    Args:
        path:      Relative path to file
        content:   Text content to write
        overwrite: If False, raises error when file exists
    """
    try:
        p = _safe_path(path)
        if p.exists() and not overwrite:
            return {"error": f"File exists and overwrite=False: {path}"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"path": path, "bytes_written": len(content.encode()), "success": True}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def file_list(path: str = ".", pattern: str = "*") -> dict:
    """
    List files in a directory.

    Args:
        path:    Directory path (relative)
        pattern: Glob pattern (e.g. "*.py")
    """
    try:
        p = _safe_path(path)
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}
        files = []
        for f in sorted(p.glob(pattern)):
            rel = str(f.relative_to(SANDBOX_ROOT))
            files.append({
                "name": f.name,
                "path": rel,
                "type": "dir" if f.is_dir() else "file",
                "size": f.stat().st_size if f.is_file() else None,
            })
        return {"path": path, "files": files, "count": len(files)}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def file_delete(path: str) -> dict:
    """Delete a file (not directories)."""
    try:
        p = _safe_path(path)
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if p.is_dir():
            return {"error": "Use rmdir for directories, not file_delete"}
        p.unlink()
        return {"path": path, "deleted": True}
    except PermissionError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}
