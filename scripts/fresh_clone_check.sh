#!/usr/bin/env bash
# make acceptance: prove D1-D15 (docs/PLAN.md) on a fresh clone of the current commit.
#
# Why a fresh clone: it catches anything that only works on this machine (an untracked file, a
# stale venv, a hand-made table). The clone gets only what a new user would add themselves: the
# raw NHTSA zips (still revalidated against NHTSA on ingest), .env, and the spend ledger so daily
# caps keep counting. Costs about $1 (one golden eval) and takes roughly 25-40 minutes.
#
# Targets in evals/accepted_misses.yaml are reported as ACCEPTED, never PASS. Exit 0 only if
# nothing FAILs.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "acceptance: commit or stash your changes first (it tests the committed code)" >&2
  exit 2
fi
SHA="$(git rev-parse HEAD)"
DEST="${SAFETYLENS_ACCEPTANCE_DIR:-$(mktemp -d)}/safetylens"
LOGS="$DEST.logs"
rm -rf "$DEST" "$LOGS"
mkdir -p "$LOGS"
echo "acceptance: $SHA -> $DEST (logs in $LOGS)"

git clone --quiet --no-hardlinks "$ROOT" "$DEST" && git -C "$DEST" checkout --quiet "$SHA"
mkdir -p "$DEST/data/raw"
cp data/raw/*.zip data/raw/manifest.json "$DEST/data/raw/"
[[ -f data/llm_usage.jsonl ]] && cp data/llm_usage.jsonl "$DEST/data/"
if [[ -f .env ]]; then cp .env "$DEST/.env"; else echo "acceptance: no .env, eval will fail" >&2; fi
cd "$DEST"

declare -a ROWS=()
FAILED=0
accepted() { grep -q "^$1:" evals/accepted_misses.yaml; }
record() {  # id, status (PASS/FAIL/ACCEPTED), detail
  ROWS+=("$(printf '%-4s %-9s %s' "$1" "$2" "$3")")
  [[ "$2" == "FAIL" ]] && FAILED=1
  printf '  %-4s %-9s %s\n' "$1" "$2" "$3"
}
step() {  # name, command...: run, log to $LOGS/name.log, return its exit code
  local name="$1"; shift
  local started=$SECONDS
  echo "== $name: $*"
  "$@" >"$LOGS/$name.log" 2>&1
  local code=$?
  echo "   exit $code in $((SECONDS - started)) s"
  return $code
}
stop() {  # kill a background process and its children (uv starts python as a child)
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //PID "$(cat /proc/$1/winpid 2>/dev/null || echo "$1")" //T //F >/dev/null 2>&1
  fi
  kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
}
latest() { ls "evals/reports/$1"-*.md 2>/dev/null | sort | tail -1; }

# D1: one-command setup on a clean checkout, then the app serves pages.
setup_start=$SECONDS
if step sync make install && step data make data-dev; then
  setup_s=$((SECONDS - setup_start))
  PORT=8765
  uv run safetylens serve --port "$PORT" >"$LOGS/serve.log" 2>&1 &
  SERVE_PID=$!
  for _ in $(seq 1 120); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep 1; done
  home="$(curl -sf "http://127.0.0.1:$PORT/" || true)"
  odi="$(uv run python -c "import duckdb; print(duckdb.connect('data/safetylens.duckdb', read_only=True).execute('select min(odino) from complaint_docs').fetchone()[0])")"
  record_page="$(curl -sf "http://127.0.0.1:$PORT/complaint/$odi" || true)"
  missing="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/no/such/page" || true)"
  stop "$SERVE_PID"
  if [[ "$home" == *"Counts are not defect rates"* && "$record_page" == *"Complaint $odi"* && "$missing" == 404 ]]; then
    record D1 PASS "install + data-dev in ${setup_s} s; serve: home, /complaint/$odi, 404 page"
  else
    record D1 FAIL "data built, but serve smoke test failed (see $LOGS/serve.log)"
  fi
else
  record D1 FAIL "make install / make data-dev failed (see $LOGS)"
fi

# D2: idempotent ingest.
if step idempotent uv run pytest tests/ingest -m idempotent -q; then
  record D2 PASS "$(tail -1 "$LOGS/idempotent.log")"
else record D2 FAIL "see $LOGS/idempotent.log"; fi

# D3: data quality.
if step dq make dq; then record D3 PASS "make dq exit 0"; else record D3 FAIL "see $LOGS/dq.log"; fi

# D4: counts match the live NHTSA API.
if step crosscheck make crosscheck; then
  record D4 PASS "$(grep -iE 'within|vehicles' "$LOGS/crosscheck.log" | tail -1)"
else record D4 FAIL "see $LOGS/crosscheck.log"; fi

# D5-D7, D9, D13 (and the D12 number): one golden eval with the real API.
step eval make eval
report="$(latest answers)"
metric() { grep -E "^$1" "$report" | head -1 | grep -oE "$2" | head -1; }
check_metric() {  # id, summary line name, awk condition on $v
  local v; v="$(metric "$2" '[0-9.]+')"
  if [[ -n "$v" ]] && awk -v v="$v" "BEGIN{exit !($3)}"; then record "$1" PASS "$2 $v"
  elif [[ -n "$v" ]] && accepted "$1"; then record "$1" ACCEPTED "$2 $v (evals/accepted_misses.yaml)"
  else record "$1" FAIL "$2 ${v:-missing}"; fi
}
if [[ -n "$report" ]]; then
  check_metric D5 numbers_grounded "v == 100"
  check_metric D6 citations_valid "v == 100"
  check_metric D7 citations_supportive "v >= 90"
  check_metric D9 golden_pass "v >= 85"
  refusals="$(metric refusals '[0-9]+/[0-9]+')"
  if [[ -n "$refusals" && "${refusals%/*}" == "${refusals#*/}" ]]; then record D9 PASS "refusals $refusals"
  else record D9 FAIL "refusals ${refusals:-missing}"; fi
  cost="$(metric 'mean cost' '[$][0-9.]+')"
  if [[ -n "$cost" ]]; then record D13 PASS "mean cost $cost/question; caps unit-tested"
  else record D13 FAIL "mean cost missing"; fi
  p95="$(grep -E '^latency p50 / p95' "$report" | sed -E 's#.*/ ([0-9.]+)s$##')"
  if [[ -z "$p95" ]]; then record D12 FAIL "p95 missing"
  elif awk -v v="$p95" 'BEGIN{exit !(v < 8)}'; then record D12 PASS "p95 ${p95} s"
  elif accepted D12; then record D12 ACCEPTED "p95 ${p95} s (target < 8 s; evals/accepted_misses.yaml)"
  else record D12 FAIL "p95 ${p95} s"; fi
else
  for d in D5 D6 D7 D9 D12 D13; do record "$d" FAIL "no eval report (see $LOGS/eval.log)"; done
fi

# D8: retrieval recall@10 on the test split.
step retrieval make eval-retrieval
rreport="$(latest retrieval)"
recall="$(grep -E '^rerank ' "$rreport" | awk '{print $4}')"
if [[ -z "$recall" ]]; then record D8 FAIL "no retrieval report (see $LOGS/retrieval.log)"
elif awk -v v="$recall" 'BEGIN{exit !(v >= 0.80)}'; then record D8 PASS "rerank recall@10 test $recall"
elif accepted D8; then record D8 ACCEPTED "rerank recall@10 test $recall (target 0.80; evals/accepted_misses.yaml)"
else record D8 FAIL "rerank recall@10 test $recall"; fi

# D10: code health.
if step check make check; then record D10 PASS "$(grep -E 'passed' "$LOGS/check.log" | tail -1 | tr -d '=')"
else record D10 FAIL "see $LOGS/check.log"; fi

# D11 (and the D15 disclaimer assertion): the browser test.
uv run playwright install chromium >"$LOGS/playwright.log" 2>&1
if step e2e make e2e; then record D11 PASS "$(tail -1 "$LOGS/e2e.log")"
else record D11 FAIL "see $LOGS/e2e.log"; fi

# D14: documentation.
if step docs make docs; then record D14 PASS "README sections, links, GIF, results table"
else record D14 FAIL "$(grep FAIL "$LOGS/docs.log" | head -3 | tr '\n' ' ')"; fi

# D15: no secrets in the repo, .env ignored, disclaimer in the UI (e2e), gitleaks green in CI.
ci="$(gh run list --commit "$SHA" --json conclusion,status --jq '.[0].conclusion' 2>/dev/null || true)"
if [[ -z "$(git ls-files .env)" ]] && git check-ignore -q .env && [[ "$ci" == success ]]; then
  record D15 PASS ".env ignored and untracked; CI (incl. gitleaks) green for $SHA"
else
  record D15 FAIL ".env tracked/not ignored, or CI not green for $SHA (got: '${ci:-no run}'; push first)"
fi

echo
echo "Acceptance for $SHA ($(date +%F))"
printf '%s\n' "${ROWS[@]}" | sort -V
echo "New reports: $report, $rreport (in the clone)"
if [[ $FAILED == 0 ]]; then echo "ACCEPTANCE PASS"; else echo "ACCEPTANCE FAIL"; fi
exit $FAILED
