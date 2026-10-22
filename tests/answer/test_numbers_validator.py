import duckdb

from safetylens.answer.numbers import canonical, citations_in, numbers_from_values, numbers_in
from safetylens.answer.validator import validate


def test_canonical_forms() -> None:
    assert canonical("1,031") == "1031"
    assert canonical("12.50") == "12.5"
    assert canonical("3.0") == "3"
    assert canonical("03") == "3"


def test_numbers_in_skips_identifiers_and_citations() -> None:
    text = (
        "There were 1,031 complaints (12.5 in May) [11500282] "
        "on the 10R80, P0700 and 4xe [22V100000]."
    )
    # 10R80 and P0700 are identifiers; "4xe" is a digit with a unit-like suffix, so 4 is checked.
    assert numbers_in(text) == {"1031", "12.5", "4"}


def test_dates_stay_whole_so_a_day_cannot_vouch_for_a_count() -> None:
    found = numbers_from_values([{"month": "2024-03-01", "complaints": 7}, "2022 FORD F-150"])
    assert {"2024-03-01", "2024-03", "2024", "7", "2022", "150"} <= found
    assert "3" not in found and "1" not in found
    assert numbers_in("The peak was 2024-03 with 7 complaints.") <= found
    assert "3" in numbers_in("3 owners describe fires.") - found


def test_number_words_and_units_are_numbers_too() -> None:
    assert numbers_in("Two owners and a dozen others; it happened twice.") == {
        "two",
        "dozen",
        "twice",
    }
    assert numbers_in("at 60mph, 3x a week, the 2nd time") == {"60", "3", "2"}


def test_citations_in_keeps_order_and_dedupes() -> None:
    assert citations_in("a [11000002] b [22V123000] c [11000002]") == ["11000002", "22V123000"]


ALLOWED_NUMBERS = {"4", "2022", "150"}
ALLOWED_IDS = {"11000001", "11000002", "22V123000"}


def test_valid_answer_has_no_errors(answer_db: duckdb.DuckDBPyConnection) -> None:
    text = "The 2022 F-150 has 4 brake complaints [11000001]; see recall [22V123000]."
    assert validate(answer_db, text, ["11000001", "22V123000"], ALLOWED_NUMBERS, ALLOWED_IDS) == []


def test_stray_and_computed_numbers_are_rejected(answer_db: duckdb.DuckDBPyConnection) -> None:
    text = "4 complaints, which is 57% of 7 [11000001]."
    (error,) = validate(answer_db, text, ["11000001"], ALLOWED_NUMBERS, ALLOWED_IDS)
    assert error.startswith("numbers not in the SQL results: 7, 57")


def test_citation_outside_evidence_is_rejected(answer_db: duckdb.DuckDBPyConnection) -> None:
    errors = validate(
        answer_db, "Owners report it [11000003].", ["11000003"], ALLOWED_NUMBERS, ALLOWED_IDS
    )
    assert errors == ["citations not in the provided evidence: 11000003"]


def test_citation_missing_from_database_is_rejected(answer_db: duckdb.DuckDBPyConnection) -> None:
    allowed = ALLOWED_IDS | {"19999999"}
    errors = validate(answer_db, "Reported [19999999].", ["19999999"], ALLOWED_NUMBERS, allowed)
    assert errors == ["citations that do not exist in the database: 19999999"]


def test_cited_but_undeclared_is_rejected(answer_db: duckdb.DuckDBPyConnection) -> None:
    errors = validate(answer_db, "Reported [11000001].", [], ALLOWED_NUMBERS, ALLOWED_IDS)
    assert errors == ["cited in the text but missing from the citations list: 11000001"]


def test_validator_rejects_spelled_out_counts(answer_db: duckdb.DuckDBPyConnection) -> None:
    (error,) = validate(
        answer_db, "Two owners report it [11000001].", ["11000001"], ALLOWED_NUMBERS, ALLOWED_IDS
    )
    assert error.startswith("numbers not in the SQL results: two")
