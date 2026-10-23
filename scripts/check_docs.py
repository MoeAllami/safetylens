"""D14: check that the README is complete and its results table matches the latest eval reports.

Why generate the table: hand-copied numbers drift from what was measured. The table between the
eval-table markers is rebuilt from evals/reports/ every time; `--write` refreshes it, and the
check fails if the committed README differs. Also checks required sections, local links and the
demo GIF.

    uv run python scripts/check_docs.py          # check (make docs)
    uv run python scripts/check_docs.py --write  # refresh the table after a new eval
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
REPORTS = ROOT / "evals" / "reports"
GIF = ROOT / "docs" / "demo.gif"
MAX_GIF_BYTES = 5_000_000
START, END = "<!-- eval-table:start -->", "<!-- eval-table:end -->"
REQUIRED_SECTIONS = [
    "## Quickstart",
    "## How it works",
    "## How answers stay honest",
    "## Data card",
    "## Results",
    "## Limitations",
    "## Costs",
    "## Development",
]


def _latest(prefix: str) -> Path:
    reports = sorted(REPORTS.glob(f"{prefix}-*.md"))
    if not reports:
        raise SystemExit(f"no {prefix} report in {REPORTS}")
    return reports[-1]


def _find(pattern: str, text: str, what: str) -> re.Match[str]:
    m = re.search(pattern, text, flags=re.MULTILINE)
    if m is None:
        raise SystemExit(f"could not read {what} from the report")
    return m


def eval_table() -> str:
    """The README results table, built only from the latest reports and the accepted misses."""
    answers_path, retrieval_path = _latest("answers"), _latest("retrieval")
    a, r = answers_path.read_text(encoding="utf-8"), retrieval_path.read_text(encoding="utf-8")
    accepted = yaml.safe_load((ROOT / "evals" / "accepted_misses.yaml").read_text("utf-8"))

    def pct(name: str) -> int:
        return int(_find(rf"^{name}\s+(\d+)%", a, name).group(1))

    refusals = _find(r"^refusals\s+(\d+)/(\d+)", a, "refusals")
    golden_n = _find(r"^golden_pass\s+\d+%.*of (\d+)", a, "golden size").group(1)
    p50, p95 = map(
        float, _find(r"^latency p50 / p95\s+([\d.]+)s / ([\d.]+)s", a, "latency").groups()
    )
    cost = _find(r"^mean cost / question\s+\$([\d.]+)", a, "cost").group(1)
    recall = _find(r"^rerank\s+[\d.]+\s+[\d.]+\s+([\d.]+)", r, "rerank recall").group(1)
    rerank_test = float(recall)
    grounded, valid = pct("numbers_grounded"), pct("citations_valid")
    supportive, golden = pct("citations_supportive"), pct("golden_pass")
    refused, oos = refusals.groups()

    rows = [
        ("D5", "Numbers grounded in SQL", "100%", f"{grounded}%", grounded == 100),
        ("D6", "Citations valid", "100%", f"{valid}%", valid == 100),
        ("D7", "Citations support the claim (LLM judge)", ">= 90%", f"{supportive}%",
         supportive >= 90),
        ("D8", "Retrieval recall@10 (test split)", ">= 0.80", f"{rerank_test:.3f}",
         rerank_test >= 0.80),
        ("D9", f"Golden questions pass (of {golden_n})", ">= 85%", f"{golden}%", golden >= 85),
        ("D9", "Out-of-scope questions refused", "all", f"{refused}/{oos}", refused == oos),
        ("D12", "Latency p95 (p50)", "< 8 s", f"{p95:.1f} s ({p50:.1f} s)", p95 < 8),
        ("D13", "Mean cost per question", "reported", f"${cost}", True),
    ]  # fmt: skip
    lines = [
        f"From `{answers_path.relative_to(ROOT).as_posix()}` and "
        f"`{retrieval_path.relative_to(ROOT).as_posix()}`.",
        "",
        "| | Check | Target | Latest | Status |",
        "|---|---|---|---|---|",
    ]
    for gate, check, target, value, ok in rows:
        status = "pass" if ok else ("accepted miss" if gate in accepted else "**FAIL**")
        lines.append(f"| {gate} | {check} | {target} | {value} | {status} |")
    return "\n".join(lines)


def problems(readme: str) -> list[str]:
    found = [f"missing section: {s}" for s in REQUIRED_SECTIONS if s not in readme]
    for target in re.findall(r"\]\(([^)\s]+)\)|src=\"([^\"]+)\"", readme):
        link = next(t for t in target if t)
        if link.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not (ROOT / link.split("#")[0]).exists():
            found.append(f"broken link: {link}")
    if not GIF.exists():
        found.append(f"missing demo GIF: {GIF.relative_to(ROOT).as_posix()}")
    elif GIF.stat().st_size > MAX_GIF_BYTES:
        found.append(f"demo GIF is {GIF.stat().st_size:,} bytes (max {MAX_GIF_BYTES:,})")
    block = re.search(re.escape(START) + r"\n(.*?)\n" + re.escape(END), readme, flags=re.DOTALL)
    if block is None:
        found.append("missing eval-table markers")
    elif block.group(1).strip() != eval_table():
        found.append("results table differs from the latest reports (run with --write)")
    return found


def main() -> int:
    readme = README.read_text(encoding="utf-8")
    if "--write" in sys.argv:
        readme = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            lambda _: f"{START}\n{eval_table()}\n{END}",
            readme,
            flags=re.DOTALL,
        )
        README.write_text(readme, encoding="utf-8", newline="\n")
    issues = problems(readme)
    for issue in issues:
        print(f"FAIL {issue}")
    print("docs OK" if not issues else f"{len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
