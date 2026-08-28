"""Research laboratory: local HTTP sources, cited claims, and evidence checks."""

from .server import (
    DATA_DIRECTORY,
    Document,
    DocumentServer,
    load_documents,
    parse_document,
    serve_documents,
)
from .tools import (
    MAX_SOURCE_CHARACTERS,
    TRUNCATION_NOTICE,
    Claim,
    FetchedSource,
    ResearchNotebook,
    build_research_tools,
    make_fetch_source,
    make_list_sources,
    make_record_claim,
    truncate_source_text,
)
from .verification import CitedClaims, unsupported_source_ids

__all__ = [
    "DATA_DIRECTORY",
    "Document",
    "DocumentServer",
    "load_documents",
    "parse_document",
    "serve_documents",
    "MAX_SOURCE_CHARACTERS",
    "TRUNCATION_NOTICE",
    "Claim",
    "FetchedSource",
    "ResearchNotebook",
    "build_research_tools",
    "make_fetch_source",
    "make_list_sources",
    "make_record_claim",
    "truncate_source_text",
    "CitedClaims",
    "unsupported_source_ids",
]
