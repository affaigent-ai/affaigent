#!/usr/bin/env python3
import json
from pathlib import Path

BASE = Path("/opt/affaigent")
INVENTORY_PATH = BASE / "logs/checks/latest_security_inventory.json"
OUT_JSON = BASE / "logs/checks/latest_security_reviewed_inventory.json"
OUT_TXT = BASE / "logs/checks/latest_security_reviewed_inventory.txt"

if not INVENTORY_PATH.exists():
    raise SystemExit(f"inventaris ontbreekt: {INVENTORY_PATH}")

items = json.loads(INVENTORY_PATH.read_text())

REDIS_GOSU_CVES = {
    "CVE-2023-24538",
    "CVE-2023-24540",
    "CVE-2024-24790",
    "CVE-2025-68121",
}

QDRANT_OPENSSL_PACKAGES = {
    "libssl3t64",
    "openssl",
    "openssl-provider-legacy",
}

def classify(item):
    component = item.get("component")
    cve = item.get("cve")
    package = item.get("package")
    target = (item.get("target") or "")

    reviewed = False
    decision = "unreviewed"
    rationale = ""
    next_action = ""

    if component == "postgres:16.13" and cve == "CVE-2025-68121" and "gosu" in target:
        reviewed = True
        decision = "temporary_accept"
        rationale = (
            "Kwetsbaarheid zit in gosu/startup-tooling. Container draait niet privileged, "
            "heeft geen extra capabilities en service is alleen localhost bereikbaar."
        )
        next_action = "herbeoordelen_bij_nieuwe_postgres_image"

    elif component == "redis:7.4.8-alpine" and cve in REDIS_GOSU_CVES and "gosu" in target:
        reviewed = True
        decision = "temporary_accept"
        rationale = (
            "Kwetsbaarheid zit in gosu/startup-tooling. Container draait niet privileged, "
            "heeft geen extra capabilities en service is alleen localhost bereikbaar."
        )
        next_action = "herbeoordelen_bij_nieuwe_redis_image"

    elif component == "qdrant/qdrant:v1.16.3" and cve == "CVE-2025-15467" and package in QDRANT_OPENSSL_PACKAGES:
        reviewed = True
        decision = "planned_for_test"
        rationale = (
            "Bekende package-fix bestaat, maar eerdere custom patchpoging brak Qdrant functioneel. "
            "Daarom niet live patchen; eerst testen in aparte testcontainer."
        )
        next_action = "bouw_aparte_qdrant_testcontainer_en_valideer_met_health_en_smoke"

    return {
        **item,
        "reviewed": reviewed,
        "decision": decision,
        "rationale": rationale,
        "next_action": next_action,
    }

reviewed_items = [classify(item) for item in items]

reviewed_items.sort(
    key=lambda x: (
        x["severity"] != "CRITICAL",
        not x["reviewed"],
        x["component"],
        x.get("cve") or "",
        x.get("package") or "",
    )
)

OUT_JSON.write_text(json.dumps(reviewed_items, indent=2))

lines = []
lines.append("Affaigent reviewed security inventory")
lines.append("")

for item in reviewed_items:
    lines.append(
        f"[{item['severity']}] {item['component']} | {item['cve']} | pkg={item['package']} | "
        f"decision={item['decision']} | reviewed={item['reviewed']} | next={item['next_action']}"
    )

OUT_TXT.write_text("\n".join(lines) + "\n")
print(OUT_TXT)
