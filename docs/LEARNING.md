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

## Template
### YYYY-MM-DD — Phase N
- **Concepts:**
- **What I'd explain to a friend:**
- **What confused me:**
- **Quiz answers + feedback:**
- **Read next:**
