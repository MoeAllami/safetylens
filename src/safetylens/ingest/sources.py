"""Which NHTSA files make up each ingest slice."""

from dataclasses import dataclass
from typing import Literal

BASE_URL = "https://static.nhtsa.gov/odi/ffdd"

Kind = Literal["complaints", "recalls"]


@dataclass(frozen=True)
class Source:
    name: str
    kind: Kind
    url: str

    @property
    def filename(self) -> str:
        return f"{self.name}.zip"


def _complaints(name: str) -> Source:
    return Source(name, "complaints", f"{BASE_URL}/cmpl/{name}.zip")


def _recalls(name: str) -> Source:
    return Source(name, "recalls", f"{BASE_URL}/rcl/{name}.zip")


DEV_SOURCES = (
    _complaints("COMPLAINTS_RECEIVED_2020-2024"),
    _complaints("COMPLAINTS_RECEIVED_2025-2026"),
    _recalls("FLAT_RCL_POST_2010"),
)

FULL_SOURCES = (
    _complaints("FLAT_CMPL"),
    _recalls("FLAT_RCL_POST_2010"),
    _recalls("FLAT_RCL_PRE_2010"),
)


def sources_for(slice_name: str) -> tuple[Source, ...]:
    if slice_name == "dev":
        return DEV_SOURCES
    if slice_name == "full":
        return FULL_SOURCES
    raise ValueError(f"unknown slice {slice_name!r}; expected 'dev' or 'full'")
