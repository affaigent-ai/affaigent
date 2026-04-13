#!/usr/bin/env python3
import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone
from urllib import request, parse
from urllib.error import URLError, HTTPError

BASE = Path("/opt/affaigent")
NOTIFICATION_PATH = BASE / "logs/checks/latest_security_notification.json"
STATE_PATH = BASE / "logs/checks/latest_security_dispatch_state.json"
RESULT_PATH = BASE / "logs/checks/latest_security_dispatch_result.json"
ENV_PATH = BASE / "infra/docker/.env"

def load_env_file(path: Path):
    data = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data

def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def resolve_chat_id(target_chat_key, env_data):
    mapping = {
        "dennis_private": env_data.get("AFFAIGENT_TELEGRAM_CHAT_ID_DENNIS_PRIVATE"),
        "shared_group": env_data.get("AFFAIGENT_TELEGRAM_CHAT_ID_SHARED_GROUP"),
        "linsey_private": env_data.get("AFFAIGENT_TELEGRAM_CHAT_ID_LINSEY_PRIVATE"),
    }
    return mapping.get(target_chat_key)

if not NOTIFICATION_PATH.exists():
    raise SystemExit(f"notificationbestand ontbreekt: {NOTIFICATION_PATH}")

notification = json.loads(NOTIFICATION_PATH.read_text())
env_file = load_env_file(ENV_PATH)

bot_token = (
    os.environ.get("AFFAIGENT_TELEGRAM_BOT_TOKEN")
    or env_file.get("AFFAIGENT_TELEGRAM_BOT_TOKEN")
    or env_file.get("TELEGRAM_BOT_TOKEN")
)

target_chat_key = notification.get("target_chat_key", "dennis_private")
chat_id = resolve_chat_id(target_chat_key, env_file)

message_text = notification.get("message_text", "")
delivery_mode = notification.get("delivery_mode", "silent")
notify_telegram = bool(notification.get("notify_telegram", False))

state_key = f"{target_chat_key}::{message_text}"
message_hash = hashlib.sha256(state_key.encode("utf-8")).hexdigest()

previous = {}
if STATE_PATH.exists():
    try:
        previous = json.loads(STATE_PATH.read_text())
    except Exception:
        previous = {}

previous_hash = previous.get("last_sent_message_hash")
already_sent_same = previous_hash == message_hash

result = {
    "generated_at": now_utc(),
    "delivery_mode": delivery_mode,
    "notify_telegram": notify_telegram,
    "target_chat_key": target_chat_key,
    "chat_id_present": bool(chat_id),
    "message_hash": message_hash,
    "sent": False,
    "reason": "",
}

if not notify_telegram or delivery_mode != "telegram":
    result["reason"] = "geen verzending nodig"
elif not bot_token:
    result["reason"] = "telegram bot token ontbreekt"
elif not chat_id:
    result["reason"] = f"chat id ontbreekt voor target_chat_key={target_chat_key}"
elif already_sent_same:
    result["reason"] = "zelfde bericht al eerder verzonden"
else:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = parse.urlencode({
        "chat_id": chat_id,
        "text": message_text,
    }).encode("utf-8")

    req = request.Request(url, data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        result["sent"] = True
        result["reason"] = "bericht verzonden"
        result["telegram_response"] = body
        STATE_PATH.write_text(json.dumps({
            "last_sent_at": now_utc(),
            "last_sent_message_hash": message_hash,
            "last_target_chat_key": target_chat_key
        }, indent=2))
    except HTTPError as e:
        result["reason"] = f"http fout: {e.code}"
    except URLError as e:
        result["reason"] = f"netwerkfout: {e.reason}"
    except Exception as e:
        result["reason"] = f"onverwachte fout: {e}"

RESULT_PATH.write_text(json.dumps(result, indent=2))
print(RESULT_PATH)
