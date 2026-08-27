from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from types import MappingProxyType
from urllib.parse import unquote, urlparse

DATA_DIRECTORY = Path(__file__).resolve().parent / "data"
LOCALHOST = "127.0.0.1"
INDEX_PATH = "/sources"
SOURCE_PREFIX = "/sources/"
CONFLICTS_FIELD = "Conflicts-With:"
SERVER_THREAD_NAME = "research-document-server"
POLL_INTERVAL_SECONDS = 0.02
SHUTDOWN_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class Document:
    source_id: str
    title: str
    text: str
    conflicts_with: tuple[str, ...] = ()


def parse_document(source_id: str, raw: str) -> Document:
    title = ""
    conflicts: tuple[str, ...] = ()
    body: list[str] = []
    for line in raw.splitlines():
        if not body and not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        if not body and line.startswith(CONFLICTS_FIELD):
            declared = line[len(CONFLICTS_FIELD) :].split(",")
            conflicts = tuple(item.strip() for item in declared if item.strip())
            continue
        if not body and not line.strip():
            continue
        body.append(line)
    return Document(
        source_id=source_id,
        title=title or source_id,
        text="\n".join(body).strip(),
        conflicts_with=conflicts,
    )


def load_documents(directory: Path = DATA_DIRECTORY) -> dict[str, Document]:
    documents: dict[str, Document] = {}
    for path in sorted(directory.glob("*.md")):
        documents[path.stem] = parse_document(
            path.stem, path.read_text(encoding="utf-8")
        )
    if not documents:
        raise ValueError(f"no synthetic sources found in {directory}")
    return documents


def _build_handler(documents: Mapping[str, Document]) -> type[BaseHTTPRequestHandler]:
    class _DocumentHandler(BaseHTTPRequestHandler):
        server_version = "ResearchLabDocuments/1.0"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in (INDEX_PATH, SOURCE_PREFIX):
                self._respond(
                    HTTPStatus.OK,
                    {
                        "sources": [
                            {"id": document.source_id, "title": document.title}
                            for document in documents.values()
                        ]
                    },
                )
                return
            if path.startswith(SOURCE_PREFIX):
                source_id = unquote(path[len(SOURCE_PREFIX) :])
                document = documents.get(source_id)
                if document is None:
                    self._respond(
                        HTTPStatus.NOT_FOUND,
                        {"error": f"unknown source: {source_id}"},
                    )
                    return
                self._respond(
                    HTTPStatus.OK,
                    {
                        "id": document.source_id,
                        "title": document.title,
                        "conflicts_with": list(document.conflicts_with),
                        "text": document.text,
                    },
                )
                return
            self._respond(HTTPStatus.NOT_FOUND, {"error": f"unknown path: {path}"})

        def _respond(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
            body = json.dumps(dict(payload), sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return _DocumentHandler


class DocumentServer:
    def __init__(
        self,
        documents: Mapping[str, Document],
        *,
        host: str = LOCALHOST,
    ) -> None:
        self._documents = dict(documents)
        self._host = host
        self._http = HTTPServer((host, 0), _build_handler(self._documents))
        self._thread = Thread(
            target=partial(self._http.serve_forever, POLL_INTERVAL_SECONDS),
            name=SERVER_THREAD_NAME,
            daemon=True,
        )
        self._started = False

    @property
    def documents(self) -> Mapping[str, Document]:
        return MappingProxyType(self._documents)

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return int(self._http.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self.port}"

    def start(self) -> None:
        if self._started:
            raise RuntimeError("document server is already started")
        self._started = True
        self._thread.start()

    def stop(self) -> None:
        if self._started and self._thread.is_alive():
            self._http.shutdown()
            self._thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        self._http.server_close()

    def __enter__(self) -> DocumentServer:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


def serve_documents(
    directory: Path = DATA_DIRECTORY,
    *,
    host: str = LOCALHOST,
) -> DocumentServer:
    return DocumentServer(load_documents(directory), host=host)
