"""
Memory module for EchoHound
"""
from .session_memory import (
    build_memory_prompt_for_user,
    get_session_memory,
    save_typed_memory,
    should_extract_memory,
    get_memory_update_prompt,
    init_session_memory,
    clear_session_memory,
)
from .user_manager import (
    memory_for_prompt,
    get_user_memory,
    write_user_memory,
    clear_user_memory,
    get_community_memory,
    write_community_memory,
    get_user_summary,
)

__all__ = [
    "build_memory_prompt_for_user", "get_session_memory", "save_typed_memory",
    "should_extract_memory", "get_memory_update_prompt", "init_session_memory",
    "clear_session_memory", "memory_for_prompt", "get_user_memory",
    "write_user_memory", "clear_user_memory", "get_community_memory",
    "write_community_memory", "get_user_summary",
]
