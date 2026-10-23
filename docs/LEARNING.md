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

### 2026-10-22 — Phase 3
- **Concepts:** lexical vs semantic retrieval (`store/queries/search_bm25.sql`, `search/search.py::bm25/dense`, `search/embed.py::SentenceTransformerEmbedder`); two-stage retrieval with reciprocal rank fusion and a cross-encoder rerank (`search/search.py::rrf/_rerank`, `search/rerank.py`); honest evaluation with pooled labels, capped recall@10 and a dev/test split (`search/evaluate.py::recall_at_k`, `RetrievalQuery.split`, `RetrievalReport.passed`).
- **Q&A:**
  - *q02: BM25 1.0, dense 0.0, why, and what if dense-only?* One complaint says the wheel "came totally out of the column"; BM25 rewards that rare word combination, the embedding is crowded out by hundreds of similar "steering locked / control arm detached" complaints. Dense-only would lose exact-detail queries. Caught by per-method columns in `make eval-retrieval`, not by unit tests (the fake embedder behaves lexically). Lexical and semantic fail on different queries; combine and measure both.
  - *Why did rerank depth 50 (0.683) score below 20 (0.775) on dev?* More candidates = more chances to promote plausible-but-wrong complaints, and rerank drops the fusion's agreement signal; also candidates beyond pool depth 20 were never judged and count as not relevant. The "unjudged in top 10" column exposes the second effect (not recorded for the depth-50 sweep). An eval can only reward what was judged.
  - *Why not tune on all 56 queries?* Picking the best of many noisy scores (one query = ~3.6 points of a 28-query mean) overfits and reports an optimistic number. Test stayed held out (dev 0.775 vs test 0.777). `passed()` gates on test, but sweeps could still peek at test (reviewer note: add `--split dev`). The number you tune on can't also be the number you report.
- **Read next:**
  - BM25: https://en.wikipedia.org/wiki/Okapi_BM25
  - Reciprocal rank fusion (Cormack et al., 2009): https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
  - Train / validation / test splits: https://developers.google.com/machine-learning/crash-course/overfitting/dividing-datasets

## Template
### YYYY-MM-DD — Phase N
- **Concepts:**
- **What I'd explain to a friend:**
- **What confused me:**
- **Quiz answers + feedback:**
- **Read next:**

### 2026-10-22 — Phase 4
- **Concepts:** structured outputs as a contract between the model and code (`answer/llm.py::AnthropicLLM.structured`, `answer/models.py::QueryPlan`, `WriterOutput`); grounding validation with retry and a deterministic fallback (`answer/numbers.py`, `answer/validator.py::validate`, `answer/pipeline.py::Engine._ask`, `answer/template.py::template_answer`); evaluating with deterministic fact checks plus an LLM judge (`answer/golden.py::check_facts`, `judge_citations`, `GoldenReport.passed`).
- **Q&A:**
  - *The planner returns `component_system: "BRAKE FAILURE"` (not a real system). What happens, and what if the pipeline didn't reset it?* The schema only guarantees shape; the value is still invented. `pipeline.py:127` resets unknown systems to None. Without it the SQL filter matches nothing, the writer says "0 complaints", and the validator passes because 0 is in the SQL rows. Only golden facts in `make eval` would catch it; no unit test covers the reset (worth adding). Structured output guarantees the shape, not the truth: check values against the DB.
  - *numbers_grounded is 100%. Why doesn't that prove the numbers are right?* The validator checks membership, not binding: "4 engine complaints" passes if 4 is the brake count somewhere in the rows. Weaknesses such as dates splitting into days were found by review, not tests. Golden facts check the structured result, not the prose, and the judge only checks citations. A check proves only what it compares.
  - *Why are facts checked on structured results and only citation support given to an LLM judge? Why is 98% D7 weaker than 100% D5?* Deterministic checks are exact, repeatable and free; "does this narrative support this sentence" needs language understanding. The judge is the same model family as the writer (shared blind spots), varies between runs, and judges only the first sentence per ODI (reviewer note). The owner's spot-check of `data/eval/judge-<date>.md` calibrates it. Use the judge only where code can't decide, and audit it.
- **Read next:**
  - Structured outputs: https://docs.claude.com/en/docs/build-with-claude/structured-outputs
  - Reducing hallucinations / grounding: https://docs.claude.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations
  - LLM-as-a-judge (Zheng et al., 2023): https://arxiv.org/abs/2306.05685

### 2026-10-22 — Phase 5
- **Concepts:** HTMX partials with a full-page fallback (`web/routes_ask.py::ask`, `HX-Request` header, `templates/_answer.html` vs `index.html`); escape model output first, then add only the markup you allow (`web/render.py::answer_html`, `templates/_chart.html` `tojson | forceescape`); measuring tail latency with per-stage timings and the noise in p95 of 40 (`answer/pipeline.py::_timed`, `answer/golden.py::GoldenReport.stage_latency`).
- **Q&A:**
  - *What breaks if `/ask` always returned the partial and ignored `HX-Request`?* If htmx fails to load or JS is off, the form posts normally and the browser shows a bare fragment: no layout, no navigation, and no disclaimer footer, which breaks D15. `test_without_htmx_the_whole_page_comes_back` catches it; the e2e test does not, because its browser runs JavaScript. A partial is an optimization; the plain request must still get a whole, compliant page.
  - *Why escape before linking citations, when the validator already checked the answer?* The validator checks numbers and citation ids, not markup: "<img src=x onerror=...> brakes [11000001]" passes it and would run script in the reader's browser if rendered raw or linked before escaping. `test_model_text_is_escaped` and `test_markup_from_the_model_is_escaped` catch that. The chart spec has the same risk in an HTML attribute (a `"` in a component name ends the attribute without `forceescape`), and no test covers a quote inside a chart value yet. Treat model text like user input: escape everything, then allow-list.
  - *Why was the 100-word prompt slower (p95 10.1 s) than the 120-word one (8.1 s)?* p95 of 40 answers is set by the 2 slowest; one retry (~3-4 s more) or one slow API reply moves it by seconds, and identical code gave writer_1 p95 from 5.8 to 7.1 s. The effect of 20 fewer words (~0.3 s) is smaller than that run-to-run noise. Nothing automated catches this: the report shows one p95 per run, so only repeated runs or the per-stage table show the spread. Compare distributions over repeated runs, not one tail number.
- **Read next:**
  - htmx documentation (hx-post, hx-target, HX-Request): https://htmx.org/docs/
  - OWASP XSS prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
  - The Tail at Scale (Dean and Barroso, 2013): https://research.google/pubs/the-tail-at-scale/
