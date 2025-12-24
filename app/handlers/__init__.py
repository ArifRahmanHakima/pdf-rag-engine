"""
App handlers package - API endpoint handlers
"""

from app.handlers.api_handlers import (
    QueryRequest,
    get_upload_handler,
    get_documents_handler,
    get_select_document_handler,
    get_list_sessions_handler,
    get_status_handler,
    get_pdf_handler,
    get_pdf_fallback_handler,
    get_delete_document_handler,
    get_query_handler,
    get_delete_session_handler,
    get_ui_handler,
)

from app.handlers.docstring_handlers import (
    get_upload_handler_docstring as get_docstring_upload_handler,
)

__all__ = [
    "QueryRequest",
    "get_upload_handler",
    "get_documents_handler",
    "get_select_document_handler",
    "get_list_sessions_handler",
    "get_status_handler",
    "get_pdf_handler",
    "get_pdf_fallback_handler",
    "get_delete_document_handler",
    "get_query_handler",
    "get_delete_session_handler",
    "get_ui_handler",
    "get_docstring_upload_handler",
]
