"""Small validators shared across ingest and answer checking."""


def is_valid_odino(value: str) -> bool:
    """Say whether ``value`` looks like an NHTSA ODI number.

    Why: the answer validator and ingest both need one definition of a well-formed ODINO,
    so citations are rejected before they reach the database lookup.
    """
    # TODO(you): return True only for a non-empty string of digits, e.g. "11500123".
    # Hint: str.isdigit() does most of the work; think about whitespace and the empty string.
    raise NotImplementedError
