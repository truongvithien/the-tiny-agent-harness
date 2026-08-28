from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from tiny_harness import FunctionTool, Risk, ToolRegistry, ToolResult

from labs.research.server import INDEX_PATH, SOURCE_PREFIX

MAX_SOURCE_CHARACTERS = 600
REQUEST_TIMEOUT_SECONDS = 5.0


def truncation_notice(limit: int) -> str:
    return f"…[TRUNCATED AT {limit} CHARACTERS]"


TRUNCATION_NOTICE = truncation_notice(MAX_SOURCE_CHARACTERS)


def truncate_source_text(text: str, limit: int = MAX_SOURCE_CHARACTERS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + truncation_notice(limit)


@dataclass(frozen=True)
class Claim:
    text: str
    source_id: str
    disputed: bool = False


@dataclass(frozen=True)
class FetchedSource:
    source_id: str
    title: str
    url: str
    conflicts_with: tuple[str, ...] = ()


class ResearchNotebook:
    def __init__(self) -> None:
        self._fetched: dict[str, FetchedSource] = {}
        self._claims: list[Claim] = []

    @property
    def fetched(self) -> Mapping[str, FetchedSource]:
        return MappingProxyType(self._fetched)

    @property
    def fetched_source_ids(self) -> tuple[str, ...]:
        return tuple(self._fetched)

    @property
    def claims(self) -> tuple[Claim, ...]:
        return tuple(self._claims)

    def remember_fetch(self, source: FetchedSource) -> None:
        self._fetched[source.source_id] = source

    def add_claim(self, claim: Claim) -> None:
        self._claims.append(claim)

    def conflicting_fetched_sources(self, source_id: str) -> tuple[str, ...]:
        cited = self._fetched.get(source_id)
        declared = set(cited.conflicts_with) if cited is not None else set()
        return tuple(
            other.source_id
            for other in self._fetched.values()
            if other.source_id != source_id
            and (other.source_id in declared or source_id in other.conflicts_with)
        )


def _get_json(url: str) -> Mapping[str, Any]:
    with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _unavailable(error: OSError) -> ToolResult:
    return ToolResult(
        ok=False,
        error=f"document server unavailable: {type(error).__name__}",
        retryable=True,
    )


def make_list_sources(base_url: str) -> FunctionTool:
    def handler(arguments: Mapping[str, Any]) -> ToolResult:
        del arguments
        try:
            payload = _get_json(f"{base_url}{INDEX_PATH}")
        except OSError as error:
            return _unavailable(error)
        rows = payload.get("sources", ())
        listing = "\n".join(f"{row['id']}: {row['title']}" for row in rows)
        return ToolResult(ok=True, output=listing or "no sources are available")

    return FunctionTool(
        name="list_sources",
        description="List the document ids and titles the source server offers.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=handler,
    )


def make_fetch_source(base_url: str, notebook: ResearchNotebook) -> FunctionTool:
    def handler(arguments: Mapping[str, Any]) -> ToolResult:
        source_id = str(arguments.get("source_id", "")).strip()
        if not source_id:
            return ToolResult(ok=False, error="fetch_source requires a source_id")
        url = f"{base_url}{SOURCE_PREFIX}{quote(source_id)}"
        try:
            payload = _get_json(url)
        except HTTPError as error:
            if error.code == 404:
                return ToolResult(ok=False, error=f"unknown source: {source_id}")
            return ToolResult(
                ok=False,
                error=f"document server returned HTTP {error.code}",
                retryable=True,
            )
        except OSError as error:
            return _unavailable(error)
        conflicts = tuple(str(item) for item in payload.get("conflicts_with", ()))
        title = str(payload.get("title", source_id))
        notebook.remember_fetch(
            FetchedSource(
                source_id=source_id,
                title=title,
                url=url,
                conflicts_with=conflicts,
            )
        )
        lines = [
            f"source_id: {source_id}",
            f"url: {url}",
            f"title: {title}",
            f"character_limit: {MAX_SOURCE_CHARACTERS}",
        ]
        if conflicts:
            lines.append(f"conflicts_with: {', '.join(conflicts)}")
        lines.append("text:")
        lines.append(truncate_source_text(str(payload.get("text", ""))))
        return ToolResult(ok=True, output="\n".join(lines))

    return FunctionTool(
        name="fetch_source",
        description=(
            "Retrieve one document by id and return its provenance header plus"
            f" its first {MAX_SOURCE_CHARACTERS} characters."
        ),
        input_schema={
            "type": "object",
            "properties": {"source_id": {"type": "string"}},
            "required": ["source_id"],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=handler,
    )


def make_record_claim(notebook: ResearchNotebook) -> FunctionTool:
    def handler(arguments: Mapping[str, Any]) -> ToolResult:
        text = str(arguments.get("claim", "")).strip()
        source_id = str(arguments.get("source_id", "")).strip()
        disputed = bool(arguments.get("disputed", False))
        if not text:
            return ToolResult(ok=False, error="record_claim requires a non-empty claim")
        if source_id not in notebook.fetched_source_ids:
            return ToolResult(
                ok=False,
                error=(
                    "cannot cite a source that was not fetched in this run: "
                    f"{source_id or '(missing)'}"
                ),
            )
        notebook.add_claim(Claim(text=text, source_id=source_id, disputed=disputed))
        conflicts = notebook.conflicting_fetched_sources(source_id)
        output = f"recorded claim {len(notebook.claims)} citing {source_id}"
        if disputed:
            output += " (marked disputed)"
        if conflicts:
            output += f"; contradicted by fetched sources: {', '.join(conflicts)}"
        return ToolResult(ok=True, output=output)

    return FunctionTool(
        name="record_claim",
        description=(
            "Record one claim together with the id of a source fetched in this"
            " run, marking it disputed when fetched sources disagree."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "source_id": {"type": "string"},
                "disputed": {"type": "boolean"},
            },
            "required": ["claim", "source_id"],
            "additionalProperties": False,
        },
        risk=Risk.READ,
        handler=handler,
    )


def build_research_tools(base_url: str, notebook: ResearchNotebook) -> ToolRegistry:
    return ToolRegistry(
        [
            make_list_sources(base_url),
            make_fetch_source(base_url, notebook),
            make_record_claim(notebook),
        ]
    )
