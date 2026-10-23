"""Turn a validated answer into safe HTML: escaped text, a little Markdown, linked citations.

Why escape first: the answer text comes from a model, so it is treated like user input. Every
character is escaped, and only then are the few patterns we allow (paragraphs, bullets, **bold**,
[citation] links) turned into tags, so a "<script>" in a draft can only ever show up as text.
"""

import re

from markupsafe import Markup, escape

from safetylens.web.records import CAMPAIGN, ODI

_CITE = re.compile(r"\[([0-9A-Za-z]{6,9})\]")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _link(match: re.Match[str], allowed: set[str]) -> str:
    cited = match.group(1).upper()
    if cited not in allowed:
        return match.group(0)
    if CAMPAIGN.fullmatch(cited):
        return f'<a href="/recall/{cited}" class="cite">[{cited}]</a>'
    if ODI.fullmatch(cited):
        return f'<a href="/complaint/{cited}" class="cite">[{cited}]</a>'
    return match.group(0)


def _inline(text: str, allowed: set[str]) -> str:
    html = str(escape(text))
    html = _BOLD.sub(r"<strong>\1</strong>", html)
    return _CITE.sub(lambda m: _link(m, allowed), html)


def answer_html(text: str, citations: list[str]) -> Markup:
    """Paragraphs and "- " bullet lists; only ids the validator accepted become links."""
    allowed = {c.upper() for c in citations}
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        bullets = [line for line in lines if line.startswith(("- ", "* "))]
        rest = [line for line in lines if not line.startswith(("- ", "* "))]
        if rest:
            blocks.append("<p>" + "<br>".join(_inline(line, allowed) for line in rest) + "</p>")
        if bullets:
            items = "".join(f"<li>{_inline(line[2:], allowed)}</li>" for line in bullets)
            blocks.append(f"<ul>{items}</ul>")
    return Markup("\n".join(blocks))  # noqa: S704 - every piece was escaped by _inline
