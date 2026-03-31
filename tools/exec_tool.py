"""
Tool: exec_tool
===============
Run shell commands safely with timeout and output capture.
Requires explicit user confirmation (see config.py CONFIRM_REQUIRED).
"""

import subprocess
import shlex
import os
from typing import Optional

# Hard limits — prevent runaway processes
DEFAULT_TIMEOUT = 30       # seconds
MAX_OUTPUT_CHARS = 10_000  # truncate beyond this

# Commands that are always blocked regardless of permissions
BLOCKED_COMMANDS = [
    "rm -rf /", "dd if=", "mkfs", ":(){:|:&};:",  # destructive
    "curl | bash", "wget | bash", "wget -O- | sh",  # remote exec
]


def exec_command(command: str, timeout: int = DEFAULT_TIMEOUT, cwd: str = None) -> dict:
    """
    Run a shell command and return stdout/stderr/exit code.

    Args:
        command: Shell command string
        timeout: Max seconds to wait (default 30)
        cwd:     Working directory (defaults to current dir)

    Returns:
        dict with stdout, stderr, exit_code, timed_out
    """
    # Safety: block destructive patterns
    for blocked in BLOCKED_COMMANDS:
        if blocked in command:
            return {
                "error": f"Blocked command pattern detected: '{blocked}'",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd(),
        )

        stdout = result.stdout
        stderr = result.stderr

        # Truncate long output
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n[...truncated at {MAX_OUTPUT_CHARS} chars]"
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + f"\n[...truncated]"

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.returncode,
            "timed_out": False,
            "command": command,
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "exit_code": -1,
            "timed_out": True,
            "command": command,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "timed_out": False,
            "command": command,
        }
