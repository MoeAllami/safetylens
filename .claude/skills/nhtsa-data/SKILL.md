---
name: nhtsa-data
description: NHTSA complaints and recalls flat-file reference for SafetyLens - download URLs, field positions, data gotchas, privacy rule. Use before writing or changing ingest, parsing, normalization, SQL queries, or anything that counts complaints.
user-invocable: false
---

# NHTSA data reference

Source listing: https://www.nhtsa.gov/nhtsa-datasets-and-apis (free, keyless, updated daily).
Copies of the data dictionaries live in `docs/data/` — trust those over this summary if they differ.

## Download URLs
Complaints (5-year sets by received date, tab-delimited .txt inside each zip):
- https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2025-2026.zip
- https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2020-2024.zip
- https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2015-2019.zip
- ...2010-2014, 2005-2009, 2000-2004, 1995-1999 (same pattern)
- Single file: https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip (~357 MB)
- Dictionary: https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt

Recalls:
- https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip
- https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_PRE_2010.zip
- Dictionary: https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt (verify field positions from this file; not yet confirmed)

Dev slice = complaints 2020-2024 + 2025-2026, recalls post-2010.

APIs (for cross-checks and deep links only, not ingest):
- https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}
- https://api.nhtsa.gov/complaints/odinumber?odinumber={odino}
- https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}
- https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber={campno}
- https://api.nhtsa.gov/products/vehicle/models?modelYear={year}&make={make}&issueType=c
No published rate limit: be polite (1 request/second, retries with backoff, cache responses).

## Complaint file layout (CMPL.txt, updated 2026-04-30)
Tab-delimited, NO header row, dates YYYYMMDD, 51 fields (49 in files before April 2026 — accept both).
Positions (1-based) we keep:
1 CMPLID (do NOT use as key — NHTSA may change it) · 2 ODINO · 3 MFR_NAME · 4 MAKETXT · 5 MODELTXT ·
6 YEARTXT (9999 = unknown) · 7 CRASH Y/N · 8 FAILDATE · 9 FIRE Y/N · 10 INJURED · 11 DEATHS ·
12 COMPDESC · 14 STATE · 16 DATEA · 17 LDATE (received) · 18 MILES · 19 OCCURENCES · 20 CDESCR (narrative) ·
21 CMPL_TYPE · 22 POLICE_RPT_YN · 23 PURCH_DT · 24 ORIG_OWNER_YN · 28 DRIVE_TRAIN · 30 FUEL_TYPE ·
31 TRANS_TYPE · 32 VEH_SPEED · 46 PROD_TYPE (V = vehicle) · 48 MEDICAL_ATTN · 49 VEHICLES_TOWED_YN ·
50 STATE_OF_INCIDENT

## Dropped at ingest (privacy) — never store, prompt, log or display
13 CITY · 15 VIN · 41-45 DEALER_NAME/TEL/CITY/STATE/ZIP · 51 VEHICLE_OPERATOR

## Gotchas
1. ODINO repeats once per component → complaint counts use `COUNT(DISTINCT odino)`.
2. CMPLID is updateable → never a key.
3. COMPDESC is hierarchical text (`SERVICE BRAKES, HYDRAULIC`); derive `component_system`
   = text before the first `,` or `:`; keep the full string too. One complaint can list several.
4. Model names vary (`F-150`, `F150`, `F-150 PICKUP`): canonical key = upper, strip spaces/hyphens,
   plus an alias table checked against the models API.
5. Encoding: decode as cp1252 with `errors="replace"`; count replaced rows in `ingest_runs`.
6. Since the 2021 cleanup, blank Y/N became `N` and blank numbers became 0 → treat MILES=0,
   VEH_SPEED=0 as unknown (NULL) in analytics.
7. YEARTXT 9999 → NULL model year; exclude from year filters.
8. Filter PROD_TYPE = 'V' for vehicle questions.

## Citation links
- Complaint: our page `/complaint/{odino}`; external JSON `https://api.nhtsa.gov/complaints/odinumber?odinumber={odino}`.
- Recall: our page `/recall/{campno}`; external `https://www.nhtsa.gov/recalls?nhtsaId={campno}`.

## Required UI disclaimer
"Complaints are unverified consumer reports filed with NHTSA. Counts are not defect rates.
Data: U.S. National Highway Traffic Safety Administration."
