"""Find the numbers in a piece of text and put them in one canonical form.

Why canonical: the SQL row says 1031 and the prose says "1,031"; "12.50" and "12.5" are the same
number. Digits glued to letters (P0700, 10R80, 4xe) are identifiers, not quantities, and are
skipped. Bracketed citations like [11500282] are removed before scanning.
"""

import json
import re
from collections.abc import Iterable
from typing import Any

NUMBER = re.compile(r"(?<![A-Za-z0-9.,])\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")
CITATION = re.compile(r"\[([0-9]{2}[A-Z][0-9]{6}|[0-9]{6,9})\]")


def canonical(token: str) -> str:
    text = token.replace(",", "")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return str(int(text)) if "." not in text else text


def numbers_in(text: str) -> set[str]:
    return {canonical(m.group(0).rstrip(",")) for m in NUMBER.finditer(CITATION.sub(" ", text))}


def numbers_from_values(values: Iterable[Any]) -> set[str]:
    """Every number that appears anywhere in some data (dates contribute year, month and day)."""
    found: set[str] = set()
    for value in values:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        found |= numbers_in(text.replace("-", " "))
    return found


def citations_in(text: str) -> list[str]:
    return list(dict.fromkeys(CITATION.findall(text)))
