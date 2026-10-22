"""Per-model prices, used only to compute what each call cost (model choice lives in settings).

Prices are USD per million tokens (input, output), from the Anthropic price list on 2026-10-06.
Cache writes cost 1.25x input and cache reads 0.1x input. An unknown model is an error, so a new
model in settings can never silently be counted as free.
"""

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class UnknownModelPrice(KeyError):
    """The model has no entry in PRICES_PER_MTOK."""


def price(model: str) -> tuple[float, float]:
    try:
        return PRICES_PER_MTOK[model]
    except KeyError as exc:
        raise UnknownModelPrice(f"no price for model {model!r}; add it to pricing.py") from exc


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    per_in, per_out = price(model)
    weighted_in = input_tokens + 1.25 * cache_write_tokens + 0.1 * cache_read_tokens
    return (weighted_in * per_in + output_tokens * per_out) / 1_000_000
