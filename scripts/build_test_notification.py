#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path("/opt/affaigent")
OUT_JSON = BASE / "logs/checks/latest_security_notification.json"
OUT_TXT = BASE / "logs/checks/latest_security_notification.txt"

ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

message_lines = [
    "Affaigent testmelding",
    f"tijd: {ts}",
    "doel: gecontroleerde Telegram test",
    "target: dennis_private",
    "",
    "Dit is een handmatige testmelding van Affaigent.",
    "Als je dit ontvangt, werkt de Telegram-dispatcher."
]

result = {
    "generated_at": ts,
    "source_decision_file": "manual_test",
    "notification_kind": "security_ops_test",
    "target_chat_key": "dennis_private",
    "delivery_mode": "telegram",
    "delivery_reason": "manual_test",
    "needs_human": False,
    "approval_required": False,
    "notify_telegram": True,
    "message_text": "\n".join(message_lines)
}

OUT_JSON.write_text(json.dumps(result, indent=2))
OUT_TXT.write_text(result["message_text"] + "\n")
print(OUT_TXT)
