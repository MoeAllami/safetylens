"""Build tiny synthetic NHTSA flat files so ingest tests need no network and no real data.

The PII markers (SECRETVIN etc.) let tests prove personal data never reaches Parquet or DuckDB.
"""

import zipfile
from collections.abc import Iterable
from pathlib import Path

PII_MARKERS = {
    13: "SECRETCITY",
    15: "SECRETVIN",
    41: "SECRETDEALER",
    42: "SECRETTEL",
    43: "SECRETDEALERCITY",
    44: "SD",
    45: "SECRETZIP",
    51: "SECRETOPERATOR",
}


def complaint_line(
    odino: str | None = "100000001",
    compdesc: str = "SERVICE BRAKES, HYDRAULIC",
    n_fields: int = 51,
    narrative: str = "BRAKES FELT SOFT",
    **overrides: str,
) -> str:
    """One complaint record; `overrides` maps 1-based position (as pN) to a value."""
    f = [""] * n_fields
    f[0] = "900000001"
    f[1] = odino or ""
    f[2] = "FORD MOTOR COMPANY"
    f[3] = "FORD"
    f[4] = "F-150"
    f[5] = "2022"
    f[6] = "N"
    f[7] = "20220301"
    f[8] = "N"
    f[9] = "0"
    f[10] = "0"
    f[11] = compdesc
    f[13] = "TX"
    f[15] = "20220310"
    f[16] = "20220309"
    f[17] = "12000"
    f[18] = "1"
    f[19] = narrative
    f[20] = "EVOQ"
    f[45] = "V"
    for pos, marker in PII_MARKERS.items():
        if pos <= n_fields:
            f[pos - 1] = marker
    for key, value in overrides.items():
        f[int(key.removeprefix("p")) - 1] = value
    if n_fields >= 50:
        f[49] = "TX"
    return "\t".join(f)


def recall_line(campno: str | None = "22V123000", n_fields: int = 29) -> str:
    f = [""] * n_fields
    f[0] = "1"
    f[1] = campno or ""
    f[2] = "FORD"
    f[3] = "F-150"
    f[4] = "2022"
    f[6] = "SERVICE BRAKES, HYDRAULIC"
    f[11] = "1000"
    f[15] = "20220401"
    f[19] = "BRAKE LINE MAY LEAK"
    return "\t".join(f)


def write_zip(path: Path, member: str, lines: Iterable[str], *, newline: str = "\r\n") -> Path:
    """Write lines as UTF-8 text inside a zip, like the current NHTSA files."""
    payload = "".join(line + newline for line in lines).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, payload)
    return path
