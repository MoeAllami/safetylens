"""Polite, resumable-by-skipping downloads of the NHTSA zips.

Why: the files are refreshed daily and are large. A conditional GET (ETag / Last-Modified) lets a
second run skip unchanged files, and writing to a temp file then renaming means a dropped
connection can never leave a half-written zip that looks valid.
"""

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
import structlog
from pydantic import BaseModel

from safetylens.ingest.sources import Source

log = structlog.get_logger()

CHUNK_BYTES = 1 << 20
MANIFEST_NAME = "manifest.json"


class ManifestEntry(BaseModel):
    etag: str | None = None
    last_modified: str | None = None
    sha256: str
    size: int


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    status: Literal["downloaded", "unchanged", "offline"]
    sha256: str
    size: int


class IncompleteDownloadError(Exception):
    """The body ended before Content-Length bytes arrived."""


class OfflineError(Exception):
    """--offline was asked for, but a file is missing or does not match its recorded checksum."""


def use_downloaded(source: Source, raw_dir: Path) -> DownloadResult:
    """Use the zip already on disk without contacting NHTSA (`ingest --offline`).

    Why: NHTSA refreshes its files daily, so a pinned snapshot is the only way to rebuild the
    exact data the golden facts were computed from. The file must match the checksum recorded
    when it was downloaded, so a truncated or edited zip is never loaded.
    """
    target = raw_dir / source.filename
    known = _read_manifest(raw_dir).get(source.filename)
    if known is None or not target.exists():
        raise OfflineError(f"{source.filename} has not been downloaded yet; run without --offline")
    digest = hashlib.sha256()
    with target.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    if digest.hexdigest() != known.sha256:
        raise OfflineError(f"{source.filename} does not match its recorded sha256")
    return DownloadResult(target, "offline", known.sha256, known.size)


def _read_manifest(raw_dir: Path) -> dict[str, ManifestEntry]:
    path = raw_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: ManifestEntry.model_validate(entry) for name, entry in data.items()}


def _write_manifest(raw_dir: Path, manifest: dict[str, ManifestEntry]) -> None:
    path = raw_dir / MANIFEST_NAME
    tmp = path.with_name(path.name + ".part")
    payload = {name: entry.model_dump() for name, entry in sorted(manifest.items())}
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _fetch_once(
    client: httpx.Client, source: Source, raw_dir: Path, manifest: dict[str, ManifestEntry]
) -> DownloadResult:
    target = raw_dir / source.filename
    known = manifest.get(source.filename)
    # identity encoding: we hash and size-check the exact bytes the server sent.
    headers = {"Accept-Encoding": "identity"}
    if known is not None and target.exists():
        if known.etag:
            headers["If-None-Match"] = known.etag
        if known.last_modified:
            headers["If-Modified-Since"] = known.last_modified

    tmp = target.with_name(target.name + ".part")
    try:
        with client.stream("GET", source.url, headers=headers) as resp:
            if resp.status_code == httpx.codes.NOT_MODIFIED and known is not None:
                return DownloadResult(target, "unchanged", known.sha256, known.size)
            resp.raise_for_status()
            digest = hashlib.sha256()
            size = 0
            with tmp.open("wb") as fh:
                for chunk in resp.iter_raw(CHUNK_BYTES):
                    fh.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            expected = resp.headers.get("content-length")
            if expected is not None and int(expected) != size:
                raise IncompleteDownloadError(f"got {size} of {expected} bytes")
            tmp.replace(target)
            manifest[source.filename] = ManifestEntry(
                etag=resp.headers.get("etag"),
                last_modified=resp.headers.get("last-modified"),
                sha256=digest.hexdigest(),
                size=size,
            )
            return DownloadResult(target, "downloaded", digest.hexdigest(), size)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def download(
    client: httpx.Client,
    source: Source,
    raw_dir: Path,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> DownloadResult:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(raw_dir)
    for attempt in range(1, attempts + 1):
        try:
            result = _fetch_once(client, source, raw_dir, manifest)
        except (httpx.TransportError, IncompleteDownloadError) as exc:
            retryable = True
            error: Exception = exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            error = exc
        else:
            _write_manifest(raw_dir, manifest)
            log.info("download", source=source.name, status=result.status, bytes=result.size)
            return result
        if not retryable or attempt == attempts:
            raise error
        log.warning(
            "download_retry", source=source.name, attempt=attempt, error=type(error).__name__
        )
        sleep(2.0**attempt)
    raise AssertionError("unreachable")  # pragma: no cover
