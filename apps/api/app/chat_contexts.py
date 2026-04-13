def _mapping() -> dict:
    return {
        "dennis_private": {
            "default_context": "dennis_work",
            "allowed_contexts": [
                "dennis_work",
                "dennis_private",
                "shared_private",
            ],
        },
        "linsey_private": {
            "default_context": "linsey_work",
            "allowed_contexts": [
                "linsey_work",
                "linsey_private",
                "shared_private",
            ],
        },
        "shared_group": {
            "default_context": "shared_private",
            "allowed_contexts": [
                "shared_private",
            ],
        },
    }


def explain_chat_context(chat_key: str) -> dict:
    mapping = _mapping()
    data = mapping.get(chat_key)
    if not data:
        return {
            "chat_key": chat_key,
            "known": False,
            "default_context": None,
            "allowed_contexts": [],
        }

    return {
        "chat_key": chat_key,
        "known": True,
        "default_context": data["default_context"],
        "allowed_contexts": data["allowed_contexts"],
    }


def get_default_context(chat_key: str) -> str | None:
    data = _mapping().get(chat_key)
    if not data:
        return None
    return data["default_context"]


def get_allowed_contexts(chat_key: str) -> list[str]:
    data = _mapping().get(chat_key)
    if not data:
        return []
    return list(data["allowed_contexts"])


def is_allowed_context(chat_key: str, identity_key: str) -> bool:
    return identity_key in get_allowed_contexts(chat_key)
