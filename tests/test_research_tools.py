from collections.abc import Iterator

import pytest

from labs.research.server import load_documents, serve_documents
from labs.research.tools import (
    MAX_SOURCE_CHARACTERS,
    TRUNCATION_NOTICE,
    Claim,
    FetchedSource,
    ResearchNotebook,
    build_research_tools,
    truncate_source_text,
)
from labs.research.verification import CitedClaims, unsupported_source_ids
from tiny_harness import (
    FinalAnswer,
    Risk,
    RunContext,
    ToolCall,
    ToolRegistry,
)

CONTEXT = RunContext("Report the nesting pair count", ("cite fetched evidence",))
SURVEY = "marsh-survey-2024"
ATLAS = "regional-bird-atlas"
MANUAL = "survey-method-manual"


@pytest.fixture
def lab() -> Iterator[tuple[ToolRegistry, ResearchNotebook]]:
    notebook = ResearchNotebook()
    with serve_documents() as server:
        yield build_research_tools(server.base_url, notebook), notebook


def notebook_with(*sources: FetchedSource) -> ResearchNotebook:
    notebook = ResearchNotebook()
    for source in sources:
        notebook.remember_fetch(source)
    return notebook


def fetched(source_id: str, *conflicts: str) -> FetchedSource:
    return FetchedSource(
        source_id=source_id,
        title=source_id,
        url=f"http://127.0.0.1:0/sources/{source_id}",
        conflicts_with=conflicts,
    )


def source_text(output: str) -> str:
    return output.split("text:\n", 1)[1]


def test_every_research_tool_is_classified_read(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, _ = lab

    names = [specification["name"] for specification in registry.specifications()]

    assert names == ["list_sources", "fetch_source", "record_claim"]
    for name in names:
        tool = registry.get(name)
        assert tool is not None
        assert tool.risk is Risk.READ


def test_list_sources_lists_every_synthetic_source(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, _ = lab

    result = registry.execute(ToolCall("list_sources", {}))

    assert result.ok
    listed = [line.split(":", 1)[0] for line in result.output.splitlines()]
    assert SURVEY in listed
    assert ATLAS in listed
    assert sorted(listed) == sorted(load_documents())


def test_fetch_source_returns_content_with_its_provenance(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, notebook = lab

    result = registry.execute(ToolCall("fetch_source", {"source_id": ATLAS}))

    assert result.ok
    assert f"source_id: {ATLAS}" in result.output
    assert f"/sources/{ATLAS}" in result.output
    assert "title: Regional Bird Atlas: Blackwater Marsh Entry" in result.output
    assert f"conflicts_with: {SURVEY}" in result.output
    assert "96 grey heron nesting pairs" in source_text(result.output)
    assert notebook.fetched_source_ids == (ATLAS,)
    assert notebook.fetched[ATLAS].url.endswith(f"/sources/{ATLAS}")


def test_fetch_source_reports_an_unknown_source_as_a_typed_failure(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, notebook = lab

    result = registry.execute(
        ToolCall("fetch_source", {"source_id": "does-not-exist"})
    )

    assert not result.ok
    assert result.error == "unknown source: does-not-exist"
    assert not result.retryable
    assert notebook.fetched_source_ids == ()


def test_fetch_source_requires_a_source_id(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, _ = lab

    result = registry.execute(ToolCall("fetch_source", {"source_id": "  "}))

    assert not result.ok
    assert result.error == "fetch_source requires a source_id"


def test_fetch_source_enforces_the_documented_character_limit(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, _ = lab

    result = registry.execute(ToolCall("fetch_source", {"source_id": SURVEY}))

    assert result.ok
    assert f"character_limit: {MAX_SOURCE_CHARACTERS}" in result.output
    body = source_text(result.output)
    assert body.endswith(TRUNCATION_NOTICE)
    assert len(body) == MAX_SOURCE_CHARACTERS + len(TRUNCATION_NOTICE)


def test_fetch_source_leaves_a_short_document_whole(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, _ = lab

    result = registry.execute(ToolCall("fetch_source", {"source_id": MANUAL}))

    assert result.ok
    assert TRUNCATION_NOTICE not in result.output


def test_truncate_source_text_names_the_limit_it_applied() -> None:
    assert truncate_source_text("abcdef", limit=10) == "abcdef"
    assert truncate_source_text("abcdef", limit=3) == "abc…[TRUNCATED AT 3 CHARACTERS]"


def test_record_claim_refuses_a_citation_for_an_unfetched_source(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, notebook = lab

    result = registry.execute(
        ToolCall(
            "record_claim",
            {"claim": "The colony has 128 pairs.", "source_id": SURVEY},
        )
    )

    assert not result.ok
    assert result.error == (
        f"cannot cite a source that was not fetched in this run: {SURVEY}"
    )
    assert notebook.claims == ()


def test_record_claim_reports_the_conflict_it_found(
    lab: tuple[ToolRegistry, ResearchNotebook],
) -> None:
    registry, notebook = lab
    registry.execute(ToolCall("fetch_source", {"source_id": SURVEY}))
    registry.execute(ToolCall("fetch_source", {"source_id": ATLAS}))

    result = registry.execute(
        ToolCall(
            "record_claim",
            {
                "claim": "The colony has 128 pairs.",
                "source_id": SURVEY,
                "disputed": True,
            },
        )
    )

    assert result.ok
    assert result.output == (
        f"recorded claim 1 citing {SURVEY} (marked disputed);"
        f" contradicted by fetched sources: {ATLAS}"
    )
    assert notebook.claims == (
        Claim("The colony has 128 pairs.", SURVEY, disputed=True),
    )


def test_unsupported_source_ids_reports_each_missing_citation_once() -> None:
    claims = (
        Claim("first", "ghost-source"),
        Claim("second", SURVEY),
        Claim("third", "ghost-source"),
        Claim("fourth", "missing-atlas"),
    )

    assert unsupported_source_ids((), (SURVEY,)) == ()
    assert unsupported_source_ids(claims, (SURVEY,)) == (
        "ghost-source",
        "missing-atlas",
    )
    assert unsupported_source_ids(claims, ()) == (
        "ghost-source",
        SURVEY,
        "missing-atlas",
    )


def test_verifier_rejects_a_report_without_any_claim() -> None:
    notebook = notebook_with(fetched(SURVEY))

    verification = CitedClaims(notebook).verify(CONTEXT, FinalAnswer("128 pairs."))

    assert not verification.accepted
    assert verification.reason == (
        "no claim was recorded, so the report carries no captured evidence"
    )


def test_verifier_rejects_a_claim_citing_an_unfetched_source() -> None:
    notebook = notebook_with(fetched(SURVEY))
    notebook.add_claim(Claim("The colony grew.", "ghost-source"))

    verification = CitedClaims(notebook).verify(
        CONTEXT, FinalAnswer("The colony grew.")
    )

    assert not verification.accepted
    assert verification.reason == (
        "claims cite sources that were never fetched in this run: ghost-source"
    )


def test_verifier_accepts_claims_backed_by_fetched_sources() -> None:
    notebook = notebook_with(fetched(SURVEY), fetched(MANUAL))
    notebook.add_claim(Claim("128 pairs were counted.", SURVEY))
    notebook.add_claim(Claim("Two observers count each colony.", MANUAL))

    verification = CitedClaims(notebook).verify(
        CONTEXT,
        FinalAnswer(f"{SURVEY} counted 128 pairs using the method in {MANUAL}."),
    )

    assert verification.accepted
    assert verification.reason == (
        "2 recorded claims cite fetched sources, 0 of them marked disputed"
    )


def test_verifier_rejects_a_contradicted_claim_that_is_not_marked_disputed() -> None:
    notebook = notebook_with(fetched(SURVEY, ATLAS), fetched(ATLAS))
    notebook.add_claim(Claim("128 pairs were counted.", SURVEY))

    verification = CitedClaims(notebook).verify(
        CONTEXT,
        FinalAnswer(f"{SURVEY} counted 128 pairs and {ATLAS} was also read."),
    )

    assert not verification.accepted
    assert verification.reason == (
        "claims contradicted by another fetched source were not recorded as"
        f" disputed: {SURVEY} (contradicted by {ATLAS})"
    )


def test_verifier_accepts_a_contradicted_claim_reported_as_disputed() -> None:
    notebook = notebook_with(fetched(SURVEY, ATLAS), fetched(ATLAS))
    notebook.add_claim(Claim("128 pairs were counted.", SURVEY, disputed=True))

    verification = CitedClaims(notebook).verify(
        CONTEXT,
        FinalAnswer(f"{SURVEY} reports 128 pairs but {ATLAS} reports 96 pairs."),
    )

    assert verification.accepted
    assert verification.reason == (
        "1 recorded claims cite fetched sources, 1 of them marked disputed"
    )


def test_verifier_requires_the_report_to_name_the_contradicting_source() -> None:
    notebook = notebook_with(fetched(SURVEY, ATLAS), fetched(ATLAS))
    notebook.add_claim(Claim("128 pairs were counted.", SURVEY, disputed=True))

    verification = CitedClaims(notebook).verify(
        CONTEXT,
        FinalAnswer(f"{SURVEY} reports 128 pairs, though the figure is disputed."),
    )

    assert not verification.accepted
    assert verification.reason == (
        f"the report does not name every source behind its claims: {ATLAS}"
    )


def test_conflict_detection_is_symmetric_between_fetched_sources() -> None:
    notebook = notebook_with(fetched(SURVEY, ATLAS), fetched(ATLAS), fetched(MANUAL))

    assert notebook.conflicting_fetched_sources(SURVEY) == (ATLAS,)
    assert notebook.conflicting_fetched_sources(ATLAS) == (SURVEY,)
    assert notebook.conflicting_fetched_sources(MANUAL) == ()


def test_a_conflict_is_invisible_until_both_sources_are_fetched() -> None:
    notebook = notebook_with(fetched(SURVEY, ATLAS))

    assert notebook.conflicting_fetched_sources(SURVEY) == ()
