"""EchoHound tool registry."""
from .web_search import web_search
from .web_fetch import web_fetch
from .file_ops import file_read, file_write, file_list, file_delete
from .exec_tool import exec_command

# Tool manifest — Claude reads these descriptions to decide which tool to call
TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web for current information. Use for news, prices, facts, anything that might have changed recently.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {"type": "integer", "description": "Number of results (1-10)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch and read the contents of a URL. Use when you need the full text of a specific page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch"},
                "max_chars": {"type": "integer", "description": "Max chars to return", "default": 8000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "file_read",
        "description": "Read a file's contents. Returns lines with optional offset/limit for large files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "offset": {"type": "integer", "description": "Starting line (1-indexed)", "default": 1},
                "limit": {"type": "integer", "description": "Max lines to return", "default": 200},
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": "Write content to a file. Creates parent directories automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "content": {"type": "string", "description": "Content to write"},
                "overwrite": {"type": "boolean", "description": "Overwrite if exists", "default": True},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "file_list",
        "description": "List files in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
                "pattern": {"type": "string", "description": "Glob pattern e.g. *.py", "default": "*"},
            },
        },
    },
    {
        "name": "exec_command",
        "description": "Run a shell command. Use for installing packages, running scripts, git operations. REQUIRES user confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Max seconds to wait", "default": 30},
            },
            "required": ["command"],
        },
    },
]

# Map tool name → function
TOOL_MAP = {
    "web_search": web_search,
    "web_fetch": web_fetch,
    "file_read": file_read,
    "file_write": file_write,
    "file_list": file_list,
    "exec_command": exec_command,
}
