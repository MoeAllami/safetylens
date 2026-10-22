"""Small validators shared across ingest and answer checking."""


def is_valid_odino(value: str) -> bool:
    """Say whether ``value`` looks like an NHTSA ODI number.

    Why: the answer validator and ingest both need one definition of a well-formed ODINO,
    so citations are rejected before they reach the database lookup.
    """
    # isdigit() alone accepts non-ASCII digits such as "²", so require ASCII as well.
    return value.isascii() and value.isdigit()
