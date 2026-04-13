#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import date, datetime, timezone
from collections import Counter

BASE = Path("/opt/affaigent")
STATUS_PATH = BASE / "logs/checks/latest_security_status.json"
REVIEWED_PATH = BASE / "logs/checks/latest_security_reviewed_inventory.json"
POLICY_PATH = BASE / "config/security/vuln_policy.yaml"
OUT_JSON = BASE / "logs/checks/latest_security_decision.json"
OUT_TXT = BASE / "logs/checks/latest_security_decision.txt"

if not STATUS_PATH.exists():
    raise SystemExit(f"statusbestand ontbreekt: {STATUS_PATH}")

status = json.loads(STATUS_PATH.read_text())
totals = status.get("totals", {})
components = status.get("components", {})

critical = int(totals.get("critical", 0))
high = int(totals.get("high", 0))

critical_total = critical
critical_reviewed = 0
critical_unreviewed = 0
decision_counts = Counter()
next_action_counts = Counter()
alerts = []
notes = []
expiring_exceptions = []

if REVIEWED_PATH.exists():
    reviewed_items = json.loads(REVIEWED_PATH.read_text())
    for item in reviewed_items:
        if item.get("severity") != "CRITICAL":
            continue
        if item.get("reviewed"):
            critical_reviewed += 1
        else:
            critical_unreviewed += 1
        decision = item.get("decision", "unknown")
        decision_counts[decision] += 1
        next_action = item.get("next_action")
        if next_action:
            next_action_counts[next_action] += 1
else:
    critical_unreviewed = critical_total

today = date.today()
if POLICY_PATH.exists():
    current_id = None
    for raw in POLICY_PATH.read_text().splitlines():
        stripped = raw.strip()
        if stripped.startswith("- id:"):
            current_id = stripped.split(":", 1)[1].strip()
        elif current_id and stripped.startswith("expires_on:"):
            value = stripped.split(":", 1)[1].strip()
            try:
                expiry = datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                expiry = None
            if expiry:
                days_left = (expiry - today).days
                if days_left < 0:
                    expiring_exceptions.append(f"uitzondering verlopen: {current_id}")
                elif days_left <= 3:
                    expiring_exceptions.append(f"uitzondering verloopt bijna: {current_id} ({days_left} dagen)")
            current_id = None

if critical_unreviewed > 0:
    alerts.append(f"{critical_unreviewed} critical findings nog onbeoordeeld")

alerts.extend(expiring_exceptions)

if critical_total > 0 and critical_reviewed == critical_total:
    notes.append(f"alle {critical_total} critical findings zijn beoordeeld")

for component, counts in components.items():
    c = int(counts.get("critical", 0))
    h = int(counts.get("high", 0))
    if c > 0:
        notes.append(f"{component}: {c} critical / {h} high")
    elif h > 0:
        notes.append(f"{component}: {h} high")

for decision, count in sorted(decision_counts.items()):
    notes.append(f"decision {decision}: {count}")

needs_human = False
notify_telegram = False
approval_required = False
approval_reason = ""
autonomous_next_step = ""

if alerts:
    overall_status = "needs_human"
    needs_human = True
    notify_telegram = True
elif decision_counts.get('planned_for_test', 0) > 0:
    overall_status = "auto_prepare"
    autonomous_next_step = "prepare_qdrant_test_track"
elif critical_total == 0 and high == 0:
    overall_status = "ok"
else:
    overall_status = "silent_log"
    autonomous_next_step = "watch_upstream_security_updates"

result = {
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source_status_file": str(STATUS_PATH),
    "source_reviewed_inventory_file": str(REVIEWED_PATH),
    "source_policy_file": str(POLICY_PATH),
    "overall_status": overall_status,
    "needs_human": needs_human,
    "notify_telegram": notify_telegram,
    "approval_required": approval_required,
    "approval_reason": approval_reason,
    "autonomous_next_step": autonomous_next_step,
    "totals": {
        "critical": critical,
        "high": high
    },
    "review": {
        "critical_total": critical_total,
        "critical_reviewed": critical_reviewed,
        "critical_unreviewed": critical_unreviewed,
        "decision_counts": dict(sorted(decision_counts.items()))
    },
    "alerts": alerts,
    "notes": notes
}

OUT_JSON.write_text(json.dumps(result, indent=2))

lines = []
lines.append(f"overall_status: {overall_status}")
lines.append(f"needs_human: {str(needs_human).lower()}")
lines.append(f"notify_telegram: {str(notify_telegram).lower()}")
lines.append(f"approval_required: {str(approval_required).lower()}")
lines.append(f"critical: {critical}")
lines.append(f"high: {high}")
lines.append(f"critical_reviewed: {critical_reviewed}")
lines.append(f"critical_unreviewed: {critical_unreviewed}")
lines.append(f"autonomous_next_step: {autonomous_next_step}")

if alerts:
    lines.append("")
    lines.append("alerts:")
    for item in alerts:
        lines.append(f"- {item}")

if notes:
    lines.append("")
    lines.append("notes:")
    for item in notes:
        lines.append(f"- {item}")

OUT_TXT.write_text("\n".join(lines) + "\n")
print(OUT_TXT)
