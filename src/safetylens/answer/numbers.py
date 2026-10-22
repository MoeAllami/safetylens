"""Find the numbers in a piece of text and put them in one canonical form.

Why canonical: the SQL row says 1031 and the prose says "1,031"; "12.50" and "12.5" are the same
number. Three things make this stricter than "find digits":
- dates are whole values: "2024-03-01" is the date (and its year), never the numbers 3 and 1,
  so a day of the month cannot vouch for an invented count;
- number words ("two owners", "a dozen") are numbers too and are reported as words;
- digits glued to a unit ("60mph", "3x", "2nd") are checked; only identifiers that mix digits
  and letters inside (10R80) or start with a letter (P0700) are skipped.
Bracketed citations like [11500282] are removed before scanning.
"""

import json
import re
from collections.abc import Iterable
from typing import Any

CITATION = re.compile(r"\[([0-9]{2}[A-Z][0-9]{6}|[0-9]{6,9})\]")
DATE = re.compile(r"(?<![\d-])(\d{4})-(\d{2})(?:-(\d{2}))?(?![\d-])")
NUMBER = re.compile(r"(?<![A-Za-z0-9.,])(\d[\d,]*(?:\.\d+)?)([A-Za-z]*)(?![A-Za-z0-9])")
NUMBER_WORDS = frozenset(
    [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "hundreds",
        "thousand",
        "thousands",
        "million",
        "millions",
        "dozen",
        "dozens",
        "half",
        "twice",
        "double",
        "triple",
    ]
)
WORD = re.compile(r"[A-Za-z]+")


def canonical(token: str) -> str:
    text = token.replace(",", "")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return str(int(text)) if "." not in text else text


def _dates(text: str) -> tuple[set[str], str]:
    """Date tokens ("2024-03-01" also yields "2024-03" and "2024"), and the text without them."""
    found: set[str] = set()
    for m in DATE.finditer(text):
        year, month, day = m.groups()
        found |= {f"{year}-{month}", year} | ({f"{year}-{month}-{day}"} if day else set())
    return found, DATE.sub(" ", text)


def numbers_in(text: str) -> set[str]:
    """Every number-like value in prose: dates, numbers (with or without a unit), number words."""
    text = CITATION.sub(" ", text)
    found, rest = _dates(text)
    for m in NUMBER.finditer(rest):
        found.add(canonical(m.group(1).rstrip(",")))
    found |= {w.lower() for w in WORD.findall(rest) if w.lower() in NUMBER_WORDS}
    return found


def numbers_from_values(values: Iterable[Any]) -> set[str]:
    """Every number that appears anywhere in some data, with dates kept whole."""
    found: set[str] = set()
    for value in values:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        dates, rest = _dates(text)
        found |= dates
        found |= {
            canonical(m.group(1).rstrip(",")) for m in NUMBER.finditer(rest) if not m.group(2)
        }
    return found


def citations_in(text: str) -> list[str]:
    return list(dict.fromkeys(CITATION.findall(text)))
