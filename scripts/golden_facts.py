"""Compute expected facts for the golden questions from SQL, using the same compute code with
explicit plans, and write a draft YAML for the owner to review.

Why a script: the facts must come from the data, not from memory, and they are tied to the
ingested snapshot (dev slice of 2026-10-21). After a re-ingest, re-run this, diff the draft
against evals/golden.yaml, and ask the owner before changing the protected file.

Usage: uv run python scripts/golden_facts.py <out.yaml>   (after `make data-dev`)
"""

import sys

import duckdb
import yaml

from safetylens.answer.compute import compute
from safetylens.answer.models import QueryPlan, VehicleRef
from safetylens.answer.resolver import resolve

con = duckdb.connect("data/safetylens.duckdb", read_only=True)


def V(make, model, y1, y2=None):
    return VehicleRef(make=make, model=model, year_from=y1, year_to=y2 or y1)


# (id, question, intent, vehicle, compare_vehicle, system, received_from, received_to, fact keys)
# fact keys: r=resolved d=distinct_complaints t=top_component s=component_system
#            p=peak_month c=campaigns_total k=campaign_in_results
SPECS = [
    (
        "g01",
        "What are the most common complaints for the 2021 Ford F-150?",
        "top_components",
        V("Ford", "F-150", 2021),
        None,
        None,
        None,
        None,
        "rdt",
    ),
    (
        "g02",
        "What problems do owners report most for the 2023 Tesla Model Y?",
        "top_components",
        V("Tesla", "Model Y", 2023),
        None,
        None,
        None,
        None,
        "rdt",
    ),
    (
        "g03",
        "What are the most common brake complaints for 2022 Ford F-150s?",
        "top_components",
        V("Ford", "F-150", 2022),
        None,
        "SERVICE BRAKES",
        None,
        None,
        "rdts",
    ),
    (
        "g04",
        "What steering problems are reported for the 2022 Honda Civic?",
        "top_components",
        V("Honda", "Civic", 2022),
        None,
        "STEERING",
        None,
        None,
        "rdts",
    ),
    (
        "g05",
        "Which components get the most complaints on the 2021 Jeep Wrangler?",
        "top_components",
        V("Jeep", "Wrangler", 2021),
        None,
        None,
        None,
        None,
        "rdt",
    ),
    (
        "g06",
        "What engine problems do 2021 Chevrolet Silverado 1500 owners report most?",
        "top_components",
        V("Chevrolet", "Silverado 1500", 2021),
        None,
        "ENGINE",
        None,
        None,
        "rdts",
    ),
    (
        "g07",
        "What are the top complaint areas for the 2023 Honda CR-V?",
        "top_components",
        V("Honda", "CR-V", 2023),
        None,
        None,
        None,
        None,
        "rdt",
    ),
    (
        "g08",
        "What are the most reported issues with the 2021 Ram 1500?",
        "top_components",
        V("Ram", "1500", 2021),
        None,
        None,
        None,
        None,
        "rdt",
    ),
    (
        "g09",
        "What are the most common air bag complaints for the 2021 Toyota Highlander?",
        "top_components",
        V("Toyota", "Highlander", 2021),
        None,
        "AIR BAGS",
        None,
        None,
        "rdts",
    ),
    (
        "g10",
        "What do owners complain about most on the 2023 Nissan Rogue?",
        "top_components",
        V("Nissan", "Rogue", 2023),
        None,
        None,
        None,
        None,
        "rdt",
    ),
    (
        "g11",
        "How did steering complaints for the 2023 Tesla Model Y change by month during 2024?",
        "trend",
        V("Tesla", "Model Y", 2023),
        None,
        "STEERING",
        "2024-01-01",
        "2024-12-31",
        "rps",
    ),
    (
        "g12",
        "Show the monthly trend of complaints filed in 2023 for the 2021 Ford F-150.",
        "trend",
        V("Ford", "F-150", 2021),
        None,
        None,
        "2023-01-01",
        "2023-12-31",
        "rp",
    ),
    (
        "g13",
        "How have complaints about the 2022 Honda Civic changed month by month?",
        "trend",
        V("Honda", "Civic", 2022),
        None,
        None,
        None,
        None,
        "rp",
    ),
    (
        "g14",
        "What is the monthly trend of power train complaints for the 2021 Ford F-150?",
        "trend",
        V("Ford", "F-150", 2021),
        None,
        "POWER TRAIN",
        None,
        None,
        "rps",
    ),
    (
        "g15",
        "How did complaints about the 2024 Honda Prologue change over time?",
        "trend",
        V("Honda", "Prologue", 2024),
        None,
        None,
        None,
        None,
        "rp",
    ),
    (
        "g16",
        "How many complaints per month were filed in 2022 about the 2021 Jeep Wrangler?",
        "trend",
        V("Jeep", "Wrangler", 2021),
        None,
        None,
        "2022-01-01",
        "2022-12-31",
        "rp",
    ),
    (
        "g17",
        "Are there recalls for the 2021 Honda CR-V airbags?",
        "recalls",
        V("Honda", "CR-V", 2021),
        None,
        "AIR BAGS",
        None,
        None,
        "rcks",
    ),
    (
        "g18",
        "What recalls cover the 2021 Ford F-150?",
        "recalls",
        V("Ford", "F-150", 2021),
        None,
        None,
        None,
        None,
        "rck",
    ),
    (
        "g19",
        "Are there any recalls on the 2023 Tesla Model Y?",
        "recalls",
        V("Tesla", "Model Y", 2023),
        None,
        None,
        None,
        None,
        "rck",
    ),
    (
        "g20",
        "Are there fuel system recalls for the 2021 Ford Bronco Sport?",
        "recalls",
        V("Ford", "Bronco Sport", 2021),
        None,
        "FUEL SYSTEM",
        None,
        None,
        "rcks",
    ),
    (
        "g21",
        "What recalls exist for the 2021 Jeep Wrangler?",
        "recalls",
        V("Jeep", "Wrangler", 2021),
        None,
        None,
        None,
        None,
        "rck",
    ),
    (
        "g22",
        "Which recalls apply to the 2021 Chevrolet Silverado 1500?",
        "recalls",
        V("Chevrolet", "Silverado 1500", 2021),
        None,
        None,
        None,
        None,
        "rck",
    ),
    (
        "g23",
        "Are there recalls for the 2024 Honda Prologue?",
        "recalls",
        V("Honda", "Prologue", 2024),
        None,
        None,
        None,
        None,
        "rck",
    ),
    (
        "g24",
        "Have there been steering recalls on the 2023 Honda CR-V?",
        "recalls",
        V("Honda", "CR-V", 2023),
        None,
        "STEERING",
        None,
        None,
        "rcks",
    ),
    (
        "g25",
        "What do 2021 Ford F-150 owners say about the transmission?",
        "examples",
        V("Ford", "F-150", 2021),
        None,
        "POWER TRAIN",
        None,
        None,
        "rds",
    ),
    (
        "g26",
        "Show me complaints about phantom braking on the 2023 Tesla Model Y.",
        "examples",
        V("Tesla", "Model Y", 2023),
        None,
        None,
        None,
        None,
        "r",
    ),
    (
        "g27",
        "What are owners saying about sticky steering on the 2022 Honda Civic?",
        "examples",
        V("Honda", "Civic", 2022),
        None,
        "STEERING",
        None,
        None,
        "rds",
    ),
    (
        "g28",
        "Show complaints about rear axle bolts breaking on the 2021 Ford F-150.",
        "examples",
        V("Ford", "F-150", 2021),
        None,
        None,
        None,
        None,
        "r",
    ),
    (
        "g29",
        "What do people report about the death wobble on 2021 Jeep Wranglers?",
        "examples",
        V("Jeep", "Wrangler", 2021),
        None,
        None,
        None,
        None,
        "r",
    ),
    (
        "g30",
        "What do owners say about the 12-volt battery dying on the 2021 Ford Bronco Sport?",
        "examples",
        V("Ford", "Bronco Sport", 2021),
        None,
        None,
        None,
        None,
        "r",
    ),
    (
        "g31",
        "Compare complaints for the 2021 Ford F-150 and the 2021 Chevrolet Silverado 1500.",
        "compare",
        V("Ford", "F-150", 2021),
        V("Chevrolet", "Silverado 1500", 2021),
        None,
        None,
        None,
        "rd",
    ),
    (
        "g32",
        "How do 2022 Tesla Model 3 complaints compare with the 2022 Tesla Model Y?",
        "compare",
        V("Tesla", "Model 3", 2022),
        V("Tesla", "Model Y", 2022),
        None,
        None,
        None,
        "rd",
    ),
    (
        "g33",
        "Compare brake complaints for the 2022 Honda Civic and the 2022 Toyota Camry.",
        "compare",
        V("Honda", "Civic", 2022),
        V("Toyota", "Camry", 2022),
        "SERVICE BRAKES",
        None,
        None,
        "rds",
    ),
    (
        "g34",
        "Compare complaints about the 2023 Honda CR-V and the 2023 Toyota RAV4.",
        "compare",
        V("Honda", "CR-V", 2023),
        V("Toyota", "RAV4", 2023),
        None,
        None,
        None,
        "rd",
    ),
]
OOS = [
    ("g35", "Is the Ford Maverick safe?"),
    ("g36", "Which truck should I buy, the F-150 or the Silverado?"),
    ("g37", "Should I worry about driving my 2021 Jeep Wrangler?"),
    ("g38", "What is the best SUV for a family?"),
    ("g39", "What is the weather in Detroit today?"),
    ("g40", "Is Tesla a good stock to buy?"),
]

items = []
for gid, q, intent, v, cv, system, rf, rt, keys in SPECS:
    vehicles = []
    for ref in [v] + ([cv] if cv else []):
        res = resolve(con, ref)
        if res.status != "ok":
            raise SystemExit(f"{gid}: vehicle did not resolve: {res.options}")
        vehicles.append(res.vehicle)
    plan = QueryPlan(
        intent=intent,
        vehicle=v,
        compare_vehicle=cv,
        component_system=system,
        received_from=rf,
        received_to=rt,
    )
    t = compute(con, plan, vehicles).tables
    facts = {}
    if "r" in keys:
        labels = [f"{x.make} {x.model_key}" for x in vehicles]
        facts["resolved"] = labels if cv else labels[0]
    if "d" in keys:
        counts = [row["complaints"] for row in t["complaint_count"]]
        facts["distinct_complaints"] = counts if cv else counts[0]
    if "t" in keys:
        facts["top_component"] = t["top_components"][0]["component"]
    if "s" in keys:
        facts["component_system"] = system
    if "p" in keys:
        m = t["monthly_trend"]
        facts["peak_month"] = max(m, key=lambda x: x["complaints"])["month"][:7] if m else None
    if "c" in keys:
        facts["campaigns_total"] = t["recalls"][0]["campaigns_total"] if t["recalls"] else 0
    if "k" in keys and t["recalls"]:
        facts["campaign_in_results"] = t["recalls"][0]["campno"]
    items.append({"id": gid, "question": q, "intent": intent, "expected_facts": facts})
    print(gid, intent, facts, file=sys.stderr)
for gid, q in OOS:
    items.append(
        {
            "id": gid,
            "question": q,
            "intent": "out_of_scope",
            "must_cite": False,
            "expected_facts": {"status": "refused"},
        }
    )
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    yaml.safe_dump({"items": items}, fh, sort_keys=False, allow_unicode=True, width=110)
