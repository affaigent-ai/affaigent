#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path("/opt/affaigent")
DECISION_PATH = BASE / "logs/checks/latest_security_decision.json"
OUT_JSON = BASE / "logs/checks/latest_security_notification.json"
OUT_TXT = BASE / "logs/checks/latest_security_notification.txt"

if not DECISION_PATH.exists():
    raise SystemExit(f"decisionbestand ontbreekt: {DECISION_PATH}")

decision = json.loads(DECISION_PATH.read_text())

overall_status = decision.get("overall_status", "unknown")
needs_human = bool(decision.get("needs_human", False))
notify_telegram = bool(decision.get("notify_telegram", False))
approval_required = bool(decision.get("approval_required", False))
autonomous_next_step = decision.get("autonomous_next_step", "")
alerts = decision.get("alerts", []) or []
notes = decision.get("notes", []) or []
review = decision.get("review", {}) or {}
totals = decision.get("totals", {}) or {}

target_chat_key = "dennis_private"
notification_kind = "security_ops"

message_lines = []
message_lines.append("Affaigent security update")
message_lines.append(f"status: {overall_status}")
message_lines.append(f"critical: {totals.get('critical', 0)}")
message_lines.append(f"high: {totals.get('high', 0)}")
message_lines.append(f"critical_reviewed: {review.get('critical_reviewed', 0)}")
message_lines.append(f"critical_unreviewed: {review.get('critical_unreviewed', 0)}")

if autonomous_next_step:
    message_lines.append(f"volgende stap: {autonomous_next_step}")

if alerts:
    message_lines.append("")
    message_lines.append("alerts:")
    for item in alerts:
        message_lines.append(f"- {item}")

if notes:
    important_notes = notes[:6]
    message_lines.append("")
    message_lines.append("samenvatting:")
    for item in important_notes:
        message_lines.append(f"- {item}")

if not notify_telegram:
    delivery_mode = "silent"
    delivery_reason = "notify_telegram=false"
else:
    delivery_mode = "telegram"
    delivery_reason = "notify_telegram=true"

result = {
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source_decision_file": str(DECISION_PATH),
    "notification_kind": notification_kind,
    "target_chat_key": target_chat_key,
    "delivery_mode": delivery_mode,
    "delivery_reason": delivery_reason,
    "needs_human": needs_human,
    "approval_required": approval_required,
    "notify_telegram": notify_telegram,
    "message_text": "\n".join(message_lines)
}

OUT_JSON.write_text(json.dumps(result, indent=2))
OUT_TXT.write_text(result["message_text"] + "\n")
print(OUT_TXT)
