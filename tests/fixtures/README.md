# Test fixtures (protected)

Real NHTSA rows used by tests that need realistic data. Edits require the owner's unlock.

- `complaints_sample.txt`: 2,000 complaint rows from `COMPLAINTS_RECEIVED_2020-2024` and
  `COMPLAINTS_RECEIVED_2025-2026` (downloaded 2026-10-21), whole complaints only (every row of a
  sampled ODINO), chosen by a stable hash of ODINO. Original bytes (UTF-8, TAB, CRLF) except
  personal-data fields 13 CITY, 15 VIN, 41-45 DEALER_*, 51 VEHICLE_OPERATOR, which are blanked.
- `recalls_sample.txt`: 200 rows from `FLAT_RCL_POST_2010`, whole campaigns, same selection rule.
  Recall files contain no personal-data fields.

Regenerate with `scripts/make_fixtures.py` (needs `make data-dev` first).
