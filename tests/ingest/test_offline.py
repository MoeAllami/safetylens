"""ingest --offline: rebuild from the pinned zips, never from a missing or altered file."""

import hashlib
from pathlib import Path

import pytest
from builders import complaint_line, write_zip

from safetylens.ingest.download import (
    ManifestEntry,
    OfflineError,
    _write_manifest,
    use_downloaded,
)
from safetylens.ingest.sources import sources_for

SOURCE = sources_for("dev")[0]


def _seed(raw: Path) -> str:
    raw.mkdir(parents=True)
    path = write_zip(raw / SOURCE.filename, "C.txt", [complaint_line()])
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_manifest(raw, {SOURCE.filename: ManifestEntry(sha256=sha, size=path.stat().st_size)})
    return sha


def test_offline_uses_the_recorded_file(tmp_path: Path) -> None:
    sha = _seed(tmp_path / "raw")
    result = use_downloaded(SOURCE, tmp_path / "raw")
    assert (result.status, result.sha256) == ("offline", sha)


def test_offline_refuses_a_changed_file(tmp_path: Path) -> None:
    _seed(tmp_path / "raw")
    with (tmp_path / "raw" / SOURCE.filename).open("ab") as fh:
        fh.write(b"tampered")
    with pytest.raises(OfflineError, match="sha256"):
        use_downloaded(SOURCE, tmp_path / "raw")


def test_offline_refuses_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(OfflineError, match="not been downloaded"):
        use_downloaded(SOURCE, tmp_path / "raw")


def test_run_ingest_offline_loads_the_pinned_zips(tmp_path: Path) -> None:
    from builders import recall_line

    from safetylens.config import Settings
    from safetylens.ingest.pipeline import run_ingest

    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    manifest = {}
    for i, source in enumerate(sources_for("dev")):
        lines = [recall_line()] if source.kind == "recalls" else [complaint_line(f"1100000{i}")]
        path = write_zip(raw / source.filename, "X.txt", lines)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest[source.filename] = ManifestEntry(sha256=sha, size=path.stat().st_size)
    _write_manifest(raw, manifest)
    reports, con = run_ingest(Settings(data_dir=tmp_path / "data"), "dev", None)
    with con:
        assert {r.download_status for r in reports} == {"offline"}
        statuses = con.execute("SELECT DISTINCT download_status FROM ingest_runs").fetchall()
        assert statuses == [("offline",)]
