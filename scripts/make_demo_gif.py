"""Record docs/demo.gif from a running app: question -> answer -> citation -> complaint record.

Why screenshots + Pillow: a GIF plays inline on GitHub, and Playwright screenshots of the real
app show exactly what a user sees. Start the app first (`make serve`); this asks one real
question, so it costs about $0.02 of the ask budget (nothing if the answer is cached).

    uv run python scripts/make_demo_gif.py --url http://127.0.0.1:8000
"""

import argparse
import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, expect, sync_playwright

QUESTION = "What are the most common complaints for a 2022 Ford F-150?"
OUT = Path(__file__).resolve().parents[1] / "docs" / "demo.gif"
WIDTH, HEIGHT = 1000, 680


def _shot(page: Page) -> Image.Image:
    return Image.open(io.BytesIO(page.screenshot())).convert("RGB")


def record(url: str) -> list[tuple[Image.Image, int]]:
    """(frame, milliseconds) pairs."""
    frames: list[tuple[Image.Image, int]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(url)
        frames.append((_shot(page), 1200))
        page.locator("#question").press_sequentially(QUESTION, delay=25)
        frames.append((_shot(page), 1200))
        page.click("button[type=submit]")
        page.wait_for_timeout(300)
        frames.append((_shot(page), 900))  # "Checking the records…"
        expect(page.locator("#answer-card")).to_be_visible(timeout=60_000)
        expect(page.locator(".chart canvas, .chart svg").first).to_be_visible(timeout=15_000)
        page.locator("#answer").scroll_into_view_if_needed()
        frames.append((_shot(page), 3500))
        page.mouse.wheel(0, 450)
        page.wait_for_timeout(400)
        frames.append((_shot(page), 2500))
        page.locator("a.cite").first.click()
        expect(page.locator(".narrative")).to_be_visible()
        frames.append((_shot(page), 3500))
        page.locator("#nhtsa-link").scroll_into_view_if_needed()
        frames.append((_shot(page), 2500))
        browser.close()
    return frames


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    frames = record(args.url)
    images = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f, _ in frames]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        OUT,
        save_all=True,
        append_images=images[1:],
        duration=[ms for _, ms in frames],
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(images)} frames)")


if __name__ == "__main__":
    main()
