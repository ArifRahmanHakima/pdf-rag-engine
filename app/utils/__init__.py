"""
App utils package - utilities for session management, text processing, and table formatting
"""

from app.utils.session_manager import (
    get_next_session_id,
    get_session_metadata,
    save_session_metadata
)

from app.utils.text_processing import (
    split_text_into_chunks,
    cleanup_llm_response,
    extract_query_keywords
)

from app.utils.table_formatting import (
    parse_and_format_pipe_table,
    format_pipe_table_html,
    build_markdown_table,
    format_section_response,
    format_table_response
)

from app.utils.table_processor import TableProcessor

__all__ = [
    # Session
    "get_next_session_id",
    "get_session_metadata",
    "save_session_metadata",
    # Text processing
    "split_text_into_chunks",
    "cleanup_llm_response",
    "extract_query_keywords",
    # Table formatting
    "parse_and_format_pipe_table",
    "format_pipe_table_html",
    "build_markdown_table",
    "format_section_response",
    "format_table_response",
    # Table processor
    "TableProcessor",
]
