import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from safetylens.ingest.download import IncompleteDownloadError, download
from safetylens.ingest.sources import Source

SOURCE = Source("FLAT_TEST", "recalls", "https://example.test/FLAT_TEST.zip")
BODY = b"zip-bytes" * 100


def _no_sleep(_: float) -> None:
    return None


@respx.mock
def test_downloads_and_records_checksum(tmp_path: Path) -> None:
    respx.get(SOURCE.url).respond(200, content=BODY, headers={"ETag": '"v1"'})
    with httpx.Client() as client:
        result = download(client, SOURCE, tmp_path)
    assert result.status == "downloaded"
    assert result.sha256 == hashlib.sha256(BODY).hexdigest()
    assert (tmp_path / SOURCE.filename).read_bytes() == BODY


@respx.mock
def test_second_run_sends_validators_and_skips_on_304(tmp_path: Path) -> None:
    route = respx.get(SOURCE.url)
    route.side_effect = [
        httpx.Response(
            200,
            content=BODY,
            headers={"ETag": '"v1"', "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"},
        ),
        httpx.Response(304),
    ]
    with httpx.Client() as client:
        first = download(client, SOURCE, tmp_path)
        second = download(client, SOURCE, tmp_path)
    assert second.status == "unchanged"
    assert second.sha256 == first.sha256
    sent = route.calls.last.request.headers
    assert sent["If-None-Match"] == '"v1"'
    assert sent["If-Modified-Since"] == "Wed, 01 Jan 2025 00:00:00 GMT"


@respx.mock
def test_partial_download_leaves_no_file(tmp_path: Path) -> None:
    respx.get(SOURCE.url).respond(
        200, content=BODY, headers={"Content-Length": str(len(BODY) + 50)}
    )
    with httpx.Client() as client, pytest.raises((IncompleteDownloadError, httpx.HTTPError)):
        download(client, SOURCE, tmp_path, attempts=1, sleep=_no_sleep)
    assert list(tmp_path.glob("*.zip*")) == []


@respx.mock
def test_retries_server_errors_then_succeeds(tmp_path: Path) -> None:
    route = respx.get(SOURCE.url)
    route.side_effect = [httpx.Response(503), httpx.Response(200, content=BODY)]
    with httpx.Client() as client:
        result = download(client, SOURCE, tmp_path, sleep=_no_sleep)
    assert result.status == "downloaded"
    assert route.call_count == 2


@respx.mock
def test_client_errors_are_not_retried(tmp_path: Path) -> None:
    route = respx.get(SOURCE.url).respond(404)
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        download(client, SOURCE, tmp_path, sleep=_no_sleep)
    assert route.call_count == 1
