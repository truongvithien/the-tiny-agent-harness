from pathlib import Path

from labs.support_triage.store import PolicyLibrary, Ticket, TicketStore


def test_store_reads_a_real_fixture_ticket() -> None:
    ticket = TicketStore().read("T-1042")

    assert isinstance(ticket, Ticket)
    assert ticket.customer == "Dana Whitfield"
    assert ticket.channel == "email"
    assert "INV-7781" in ticket.body


def test_store_lists_at_least_four_sorted_ticket_ids() -> None:
    ids = TicketStore().ticket_ids()

    assert len(ids) >= 4
    assert ids == tuple(sorted(set(ids)))
    assert "T-1042" in ids


def test_store_returns_none_for_an_unknown_ticket_without_raising() -> None:
    assert TicketStore().read("T-9999") is None


def test_store_matches_a_ticket_id_after_trimming_and_case_folding() -> None:
    ticket = TicketStore().read("  t-1043 ")

    assert ticket is not None
    assert ticket.ticket_id == "T-1043"


def test_store_reads_only_the_directory_it_is_given(tmp_path: Path) -> None:
    store = TicketStore(tmp_path)

    assert store.ticket_ids() == ()
    assert store.read("T-1042") is None


def test_policy_search_returns_an_excerpt_with_its_source_file() -> None:
    excerpts = PolicyLibrary().search("duplicate charge")

    assert len(excerpts) == 1
    assert excerpts[0].source == "billing-refunds.md"
    assert excerpts[0].heading == "Duplicate charges"
    assert "refunded in full" in excerpts[0].text


def test_policy_library_holds_at_least_three_markdown_sources() -> None:
    sources = PolicyLibrary().sources()

    assert len(sources) >= 3
    assert all(source.endswith(".md") for source in sources)


def test_policy_search_is_case_insensitive_and_bounded() -> None:
    excerpts = PolicyLibrary().search("REFUND", limit=2)

    assert len(excerpts) == 2
    assert {excerpt.source for excerpt in excerpts} == {"billing-refunds.md"}


def test_policy_search_without_a_match_returns_no_excerpts() -> None:
    assert PolicyLibrary().search("quantum tunnelling") == ()
    assert PolicyLibrary().search("   ") == ()


def test_policy_excerpts_never_include_the_document_title() -> None:
    headings = {excerpt.heading for excerpt in PolicyLibrary().excerpts()}

    assert "Billing and refunds" not in headings
    assert "Locked accounts" in headings
