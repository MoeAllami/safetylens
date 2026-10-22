"""Write the golden-eval results: a terminal summary, the committed report, the judge review.

Why two files: the committed report (evals/reports/) has numbers and failure reasons only; the
judge review contains narrative excerpts for the owner's spot-check, so it goes under the
git-ignored data/ directory.
"""

from pathlib import Path

from safetylens.answer.golden import GoldenReport


def format_summary(report: GoldenReport) -> str:
    m = report.metrics()
    lines = [
        f"numbers_grounded      {m['numbers_grounded']:.0%}  (target 100%)",
        f"citations_valid       {m['citations_valid']:.0%}  (target 100%)",
        f"citations_supportive  {m['citations_supportive']:.0%}  (target >= 90%)",
        f"golden_pass           {m['golden_pass']:.0%}  (target >= 85%) of {len(report.items)}",
        f"refusals              {m['refusals_correct']:.0f}/{m['refusals_total']:.0f}",
        f"first_draft_ok        {m['first_draft_ok']:.0%}  (writer passed validation first time)",
        f"latency p50 / p95     {m['p50_latency_s']:.1f}s / {m['p95_latency_s']:.1f}s",
        f"mean cost / question  ${m['mean_cost_usd']:.4f}  "
        f"(+ judge ${report.judge_cost_usd:.4f} total)",
        "PASS" if report.passed() else "FAIL",
    ]
    return "\n".join(lines)


def write_markdown(report: GoldenReport, report_dir: Path) -> Path:
    """Numbers, statuses and failure reasons only; never narratives."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"answers-{report.date.isoformat()}.md"
    rows = [
        f"| {i.id} | {i.intent_expected} | {i.status} | {'pass' if i.passed else 'FAIL'} | "
        f"{i.supported}/{i.judged} | {i.latency_s:.1f} | {i.cost_usd:.4f} | "
        f"{'; '.join(i.failures)} |"
        for i in report.items
    ]
    body = [
        f"# Answer eval {report.date.isoformat()}",
        "",
        "```",
        format_summary(report),
        "```",
        "",
        "| id | intent | status | result | supported | latency s | cost $ | failures |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
    ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return path


def write_judge_review(report: GoldenReport, review_dir: Path) -> Path:
    """Every judge verdict with its sentence and a narrative excerpt, for the owner's spot-check.

    Contains narratives, so it is written under data/ (git-ignored), never into evals/reports/.
    """
    review_dir.mkdir(parents=True, exist_ok=True)
    path = review_dir / f"judge-{report.date.isoformat()}.md"
    body = [f"# Judge verdicts {report.date.isoformat()}", ""]
    for item in report.items:
        for v in item.verdicts:
            mark = "SUPPORTED" if v.supported else "NOT SUPPORTED"
            body += [
                f"## {v.item_id} [{v.odino}] {mark}",
                f"- claim: {v.claim}",
                f"- judge: {v.reason}",
                f"- narrative: {v.narrative_excerpt}",
                "",
            ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return path
