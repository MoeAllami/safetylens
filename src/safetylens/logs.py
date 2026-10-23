"""One place to configure structlog: readable on a terminal, JSON lines everywhere else.

Why a redaction step: CLAUDE.md rule 4 says narratives and personal fields never reach logs.
Call sites already log only ids, counts and timings; this processor is the safety net that drops
any forbidden key before it is rendered, so a future careless `log.info(..., narrative=...)`
cannot leak.
"""

import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

FORBIDDEN = frozenset(
    {"narrative", "question", "text", "answer", "prompt", "system", "user", "vin", "city"}
)
FORBIDDEN_PREFIXES = ("dealer", "operator", "vehicle_operator")


def redact(_logger: Any, _method: str, event: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(event):
        name = key.lower()
        if name in FORBIDDEN or name.startswith(FORBIDDEN_PREFIXES):
            event[key] = "[redacted]"
    return event


class _Stderr:
    """Looks up sys.stderr on every write, so a replaced stream (tests, CLI runners) is honoured."""

    def write(self, text: str) -> int:
        return sys.stderr.write(text)

    def flush(self) -> None:
        sys.stderr.flush()


def configure(json_output: bool | None = None) -> None:
    """JSON when stderr is not a terminal (CI, Docker, piped output), console colours otherwise."""
    if json_output is None:
        json_output = not sys.stderr.isatty()
    renderer: Any = (
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact,
            renderer,
        ],
        logger_factory=structlog.PrintLoggerFactory(file=_Stderr()),  # type: ignore[arg-type]
        cache_logger_on_first_use=False,
    )
