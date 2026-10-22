# Learning log

One entry per phase, written in your own words (the `/learn` skill helps).

### 2026-10-21 — Phase 0
- **Concepts:** pytest markers and `--strict-markers` (`pyproject.toml`, `Makefile` `test-fast`); `mypy --strict` as a type gate (`validate.py`); secrets in git history (`.gitignore`, gitleaks in `.pre-commit-config.yaml` and `ci.yml`).
- **Quiz answers + feedback:**
  - *Forgotten `network` marker:* "typos would not be caught. should fail check in CI." Feedback: `--strict-markers` does catch typo'd marker names at collection. A forgotten marker is not caught anywhere: `test-fast` runs the test, and CI runs everything with internet, so it likely passes. Only a socket-blocking `conftest.py` would enforce it.
  - *mypy passes on `return True`:* "it guarantees type safety, The CI would catch it?" Feedback: right that mypy checks types, not behavior. What catches the bug is the test failing in `pytest`; CI just makes sure the test runs. Types and tests are complementary.
  - *`.env` committed, then `git rm`:* "not, it would still be in history, they should remove from history. adding env to gitnore". Feedback: right that history keeps it. Missing: revoke and rotate the key first, since rewriting history does not un-leak it, then rewrite and force-push. `.gitignore` prevents the accident but does nothing for an already-tracked file; gitleaks pre-commit blocks the commit, CI gitleaks only catches it after the push.
- **Read next:**
  - Markers: https://docs.pytest.org/en/stable/how-to/mark.html
  - mypy strict: https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict
  - Removing sensitive data: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

### 2026-10-22 — Phase 1
- **Concepts:** idempotent ingest (`store/db.py::load_raw_table`, `CREATE OR REPLACE` in a transaction, checksum in `summary_complaints_raw.sql`); table grain (one row = complaint x product x component; `COUNT(DISTINCT odino)`; `dq_duplicate_components.sql` scoped to `prod_type = 'V'`); character encodings and mojibake (`ingest/flatfile.py::_iter_lines`, UTF-8 per line with cp1252 fallback).
- **Format:** owner asked for questions and answers together (no quiz this time).
- **Q&A:**
  - *`INSERT` instead of `CREATE OR REPLACE`?* Each run appends a copy: 1,250,274 rows after two runs, distinct ODINO unchanged. `make dq` duplicate check and the idempotency test catch it; distinct counts, missing-key and PII checks do not. Distinct counts can hide duplication.
  - *Why is `sum(deaths) FROM complaints_raw` wrong?* `deaths` is per complaint but repeats per component/product row, and non-vehicle rows are mixed in. Reduce to one row per ODINO (`max(deaths) ... GROUP BY odino`, `prod_type = 'V'`) before summing. Always ask "what is one row?" first.
  - *Why decide encoding per line?* Files can mix old cp1252 and new UTF-8 records. Risk: a cp1252 line that happens to be valid UTF-8 gets misread (`C3 A9` = `Ã©` vs `é`); rare, and `rows_cp1252` in `ingest_runs` makes the fallback visible.
- **Read next:**
  - Idempotency / table replacement: https://duckdb.org/docs/stable/sql/statements/create_table
  - Grain: https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/grain/
  - Encodings: https://www.joelonsoftware.com/2003/10/08/the-absolute-minimum-every-software-developer-absolutely-positively-must-know-about-unicode-and-character-sets-no-excuses/

### 2026-10-22 — Phase 2
- **Concepts:** golden tests vs snapshots, and test oracles (`tests/analytics/test_templates.py`, `test_real_sample_oracle.py`); parameterized SQL templates with optional filters `$x IS NULL OR col = $x` (`store/queries/top_components.sql`, `analytics/templates.py::_rows`, `count_rows.sql` via `query_table(?)`); cross-checking against an external reference with data minimization (`crosscheck/crosscheck.py::api_distinct_odis`, `crosscheck/nhtsa_api.py`).
- **Q&A:**
  - *Why hand-computed expectations instead of pasting the template's output?* A snapshot locks in bugs (a `count(*)` version would record 6 and pass forever); the hand-computed `test_complaint_count` asserts 5. The oracle only catches bugs where its logic differs, so the hand-made traps cover shared misconceptions. Expected values must come from a source independent of the code under test.
  - *Why `$x IS NULL OR col = $x` instead of appending SQL strings?* String-building lets planner output like `BRAKES' OR '1'='1` become SQL (injection, and effectively LLM-written SQL). Bound parameters keep values as data. NULL never compares true, so year filters drop unknown (9999) years for free. No test yet tries an injection-shaped value; add one in Phase 4.
  - *How could the crosscheck pass with wrong numbers, or fail with right ones?* Both sides come from NHTSA, so shared NHTSA errors agree; the check proves we reproduce NHTSA, not reality. A 2019 model year would fail because its complaints were received before the 2020+ dev slice; API live-vs-snapshot lag is absorbed by 2% and the 450-complaint minimum. Only manual `make crosscheck` catches this; CI never runs it.
- **Read next:**
  - Test oracles: https://en.wikipedia.org/wiki/Test_oracle
  - SQL injection and parameters: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
  - NHTSA datasets and APIs: https://www.nhtsa.gov/nhtsa-datasets-and-apis

## Template
### YYYY-MM-DD — Phase N
- **Concepts:**
- **What I'd explain to a friend:**
- **What confused me:**
- **Quiz answers + feedback:**
- **Read next:**
