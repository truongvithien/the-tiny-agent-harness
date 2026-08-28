import json
import socket
import threading
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from labs.research.server import (
    SERVER_THREAD_NAME,
    load_documents,
    parse_document,
    serve_documents,
)


def read_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8"))


def running_thread_names() -> set[str]:
    return {thread.name for thread in threading.enumerate()}


def test_synthetic_sources_include_a_conflict_and_an_incomplete_source() -> None:
    documents = load_documents()

    assert len(documents) >= 5
    assert documents["marsh-survey-2024"].conflicts_with == ("regional-bird-atlas",)
    assert documents["regional-bird-atlas"].conflicts_with == ("marsh-survey-2024",)
    assert "no total for the season" in documents["warden-field-notes"].text


def test_parse_document_separates_title_metadata_and_prose() -> None:
    document = parse_document(
        "demo",
        "# Demo Title\n\nConflicts-With: other-source, third-source\n\nBody line.\n",
    )

    assert document.title == "Demo Title"
    assert document.conflicts_with == ("other-source", "third-source")
    assert document.text == "Body line."


def test_server_binds_an_ephemeral_port_on_loopback_only() -> None:
    with serve_documents() as server:
        host = server.host
        port = server.port
        base_url = server.base_url

    assert host == "127.0.0.1"
    assert port > 0
    assert base_url == f"http://127.0.0.1:{port}"


def test_two_servers_bind_different_ephemeral_ports() -> None:
    with serve_documents() as first, serve_documents() as second:
        assert first.port != second.port


def test_server_serves_the_source_index_and_one_document() -> None:
    with serve_documents() as server:
        index = read_json(f"{server.base_url}/sources")
        document = read_json(f"{server.base_url}/sources/regional-bird-atlas")

    assert "marsh-survey-2024" in [row["id"] for row in index["sources"]]
    assert document["title"] == "Regional Bird Atlas: Blackwater Marsh Entry"
    assert document["conflicts_with"] == ["marsh-survey-2024"]
    assert "96 grey heron nesting pairs" in document["text"]


def test_server_returns_404_for_an_unknown_document() -> None:
    with serve_documents() as server:
        with pytest.raises(HTTPError) as raised:
            read_json(f"{server.base_url}/sources/does-not-exist")

    assert raised.value.code == 404


def test_server_leaves_no_thread_or_listening_socket_behind() -> None:
    before = running_thread_names()

    with serve_documents() as server:
        port = server.port
        read_json(f"{server.base_url}/sources")
        assert SERVER_THREAD_NAME in running_thread_names()

    assert SERVER_THREAD_NAME not in running_thread_names()
    assert running_thread_names() - before == set()
    with socket.socket() as probe:
        probe.settimeout(2.0)
        assert probe.connect_ex(("127.0.0.1", port)) != 0


def test_server_shuts_down_when_its_block_raises() -> None:
    before = running_thread_names()
    ports: list[int] = []

    with pytest.raises(RuntimeError, match="scenario failed"):
        with serve_documents() as server:
            ports.append(server.port)
            raise RuntimeError("scenario failed")

    assert SERVER_THREAD_NAME not in running_thread_names()
    assert running_thread_names() - before == set()
    with socket.socket() as probe:
        probe.settimeout(2.0)
        assert probe.connect_ex(("127.0.0.1", ports[0])) != 0
