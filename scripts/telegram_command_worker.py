#!/usr/bin/env python3
import json
import time
from pathlib import Path
from urllib import request, parse
from urllib.error import HTTPError, URLError

BASE = Path("/opt/affaigent")
ENV_PATH = BASE / "infra/docker/.env"
STATE_PATH = BASE / "data/telegram/poll_state.json"

API_BASE_URL = "http://127.0.0.1:8000"


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2))


def tg_api(token: str, method: str, params: dict | None = None) -> dict:
    params = params or {}
    url = f"https://api.telegram.org/bot{token}/{method}"
    if method == "getUpdates":
        query = parse.urlencode(params)
        if query:
            url = f"{url}?{query}"
        req = request.Request(url, method="GET")
    else:
        payload = parse.urlencode(params).encode("utf-8")
        req = request.Request(url, data=payload, method="POST")

    with request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def api_get(path: str, query: dict | None = None) -> dict:
    query = query or {}
    qs = parse.urlencode(query)
    url = f"{API_BASE_URL}{path}"
    if qs:
        url = f"{url}?{qs}"
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def api_post(path: str, query: dict | None = None) -> dict:
    query = query or {}
    qs = parse.urlencode(query)
    url = f"{API_BASE_URL}{path}"
    if qs:
        url = f"{url}?{qs}"
    req = request.Request(url, data=b"", method="POST")
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def api_post_json(path: str, payload: dict) -> dict:
    url = f"{API_BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def resolve_chat_key(chat_id: int, env_data: dict[str, str]) -> str | None:
    mapping = {
        env_data.get("AFFAIGENT_TELEGRAM_CHAT_ID_DENNIS_PRIVATE"): "dennis_private",
        env_data.get("AFFAIGENT_TELEGRAM_CHAT_ID_SHARED_GROUP"): "shared_group",
        env_data.get("AFFAIGENT_TELEGRAM_CHAT_ID_LINSEY_PRIVATE"): "linsey_private",
    }
    return mapping.get(str(chat_id))


def send_message(token: str, chat_id: int, text: str) -> None:
    tg_api(token, "sendMessage", {"chat_id": str(chat_id), "text": text})


def build_start_text(chat_key: str, current: dict) -> str:
    allowed = ", ".join(current.get("allowed_contexts", []))
    selected = current.get("selected_context")
    return (
        "Affi is gestart.\n"
        f"chat_key: {chat_key}\n"
        f"huidige context: {selected}\n"
        f"toegestane contexten: {allowed}\n\n"
        "Beschikbare commando's:\n"
        "/health\n"
        "/context\n"
        "/work\n"
        "/private\n"
        "/shared"
    )


def handle_command(command: str, chat_key: str) -> str:
    if command == "/health":
        data = api_get("/health")
        return f"Affi health: {data.get('status')} | app: {data.get('app')} | env: {data.get('env')}"

    if command == "/context":
        data = api_get("/chat-context/current", {"chat_key": chat_key})
        allowed = ", ".join(data.get("allowed_contexts", []))
        return (
            f"huidige context: {data.get('selected_context')}\n"
            f"default: {data.get('default_context')}\n"
            f"toegestaan: {allowed}"
        )

    if command == "/work":
        target = {
            "dennis_private": "dennis_work",
            "linsey_private": "linsey_work",
            "shared_group": None,
        }.get(chat_key)
        if not target:
            return "Deze chat kan niet naar een werkcontext schakelen."
        data = api_post("/chat-context/select", {"chat_key": chat_key, "identity_key": target})
        return f"context gezet op: {data.get('selected_context')}"

    if command == "/private":
        target = {
            "dennis_private": "dennis_private",
            "linsey_private": "linsey_private",
            "shared_group": None,
        }.get(chat_key)
        if not target:
            return "Deze chat kan niet naar een privécontext schakelen."
        data = api_post("/chat-context/select", {"chat_key": chat_key, "identity_key": target})
        return f"context gezet op: {data.get('selected_context')}"

    if command == "/shared":
        data = api_post("/chat-context/select", {"chat_key": chat_key, "identity_key": "shared_private"})
        return f"context gezet op: {data.get('selected_context')}"

    if command == "/start":
        current = api_get("/chat-context/current", {"chat_key": chat_key})
        return build_start_text(chat_key, current)

    return "Onbekend commando."


def handle_text_message(chat_key: str, text: str) -> str:
    current = api_get("/chat-context/current", {"chat_key": chat_key})
    identity_key = current.get("selected_context")
    if not identity_key:
        raise RuntimeError("Geen geselecteerde context gevonden voor deze chat")

    result = api_post_json(
        "/chat/respond",
        {
            "identity_key": identity_key,
            "message": text,
        },
    )

    return (
        result.get("reply")
        or result.get("response")
        or result.get("text")
        or result.get("message")
        or "Affi gaf een leeg antwoord terug."
    )


def main() -> int:
    env_data = load_env_file(ENV_PATH)
    token = env_data.get("AFFAIGENT_TELEGRAM_BOT_TOKEN") or env_data.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("telegram bot token ontbreekt in .env")

    while True:
        try:
            state = read_json(STATE_PATH, {"last_update_id": 0})
            offset = int(state.get("last_update_id", 0)) + 1

            updates = tg_api(token, "getUpdates", {"offset": offset, "timeout": 20})
            results = updates.get("result", [])

            last_seen = state.get("last_update_id", 0)

            for item in results:
                update_id = int(item.get("update_id", 0))
                if update_id > last_seen:
                    last_seen = update_id

                message = item.get("message") or {}
                text = (message.get("text") or "").strip()
                chat = message.get("chat") or {}
                chat_id = chat.get("id")

                if not chat_id or not text:
                    continue

                chat_key = resolve_chat_key(chat_id, env_data)
                if not chat_key:
                    send_message(token, chat_id, "Deze chat is nog niet gekoppeld aan een Affi context.")
                    continue

                try:
                    if text.startswith("/"):
                        command = text.split()[0]
                        reply = handle_command(command, chat_key)
                    else:
                        reply = handle_text_message(chat_key, text)
                except HTTPError as e:
                    reply = f"API fout: HTTP {e.code}"
                except URLError as e:
                    reply = f"Netwerkfout richting API: {e.reason}"
                except Exception as e:
                    reply = f"Onverwachte fout: {e}"

                send_message(token, chat_id, reply)

            write_json(STATE_PATH, {"last_update_id": last_seen})

        except Exception as e:
            print(f"telegram worker fout: {e}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
