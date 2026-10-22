"""Which fields we keep from each flat file, by 1-based position in the NHTSA dictionaries.

Complaint positions 13 CITY, 15 VIN, 41-45 DEALER_*, 51 VEHICLE_OPERATOR are deliberately absent:
they are personal data and must never leave the parser (CLAUDE.md rule 4).
Dictionaries: docs/data/CMPL.txt and docs/data/RCL.txt.
"""

from safetylens.ingest.flatfile import Column

# Files before April 2026 have 49 fields; newer ones have 51.
COMPLAINT_FIELD_COUNTS = frozenset({49, 51})

COMPLAINT_COLUMNS = (
    Column("cmplid", 1),
    Column("odino", 2),
    Column("mfr_name", 3),
    Column("maketxt", 4),
    Column("modeltxt", 5),
    Column("yeartxt", 6, "int"),
    Column("crash", 7),
    Column("faildate", 8, "date"),
    Column("fire", 9),
    Column("injured", 10, "int"),
    Column("deaths", 11, "int"),
    Column("compdesc", 12),
    Column("state", 14),
    Column("datea", 16, "date"),
    Column("ldate", 17, "date"),
    Column("miles", 18, "int"),
    Column("occurences", 19, "int"),
    Column("cdescr", 20),
    Column("cmpl_type", 21),
    Column("police_rpt_yn", 22),
    Column("purch_dt", 23, "date"),
    Column("orig_owner_yn", 24),
    Column("drive_train", 28),
    Column("fuel_type", 30),
    Column("trans_type", 31),
    Column("veh_speed", 32, "int"),
    Column("prod_type", 46),
    Column("medical_attn", 48),
    Column("vehicles_towed_yn", 49),
    Column("state_of_incident", 50),  # only present in 51-field files; NULL otherwise
)

RECALL_FIELD_COUNTS = frozenset({29})

RECALL_COLUMNS = (
    Column("record_id", 1, "int"),
    Column("campno", 2),
    Column("maketxt", 3),
    Column("modeltxt", 4),
    Column("yeartxt", 5, "int"),
    Column("mfgcampno", 6),
    Column("compname", 7),
    Column("mfgname", 8),
    Column("bgman", 9, "date"),
    Column("endman", 10, "date"),
    Column("rcltypecd", 11),
    Column("potaff", 12, "int"),
    Column("odate", 13, "date"),
    Column("influenced_by", 14),
    Column("mfgtxt", 15),
    Column("rcdate", 16, "date"),
    Column("datea", 17, "date"),
    Column("rpno", 18),
    Column("fmvss", 19),
    Column("desc_defect", 20),
    Column("consequence_defect", 21),
    Column("corrective_action", 22),
    Column("notes", 23),
    Column("rcl_cmpt_id", 24),
    Column("mfr_comp_name", 25),
    Column("mfr_comp_desc", 26),
    Column("mfr_comp_ptno", 27),
    Column("do_not_drive", 28),
    Column("park_outside", 29),
)
