import os
import time
from typing import Any

import httpx
from google import genai

from app.model_router import resolve_profiles


def _system_prompt(identity_key: str, retrieved_context: str | None = None) -> str:
    base = (
        "Je bent Affi, een persoonlijke AI-assistent. "
        "Geef erg goede, feitelijk zorgvuldige antwoorden in het Nederlands. "
        "Minimaliseer hallucinaties, maak geen ongegronde aannames als iets controleerbaar is, "
        "en wees helder over onzekerheid. "
        f"De actieve context is: {identity_key}."
    )

    if not retrieved_context:
        return base

    return (
        base
        + " Gebruik de opgehaalde context hieronder alleen als die echt relevant is voor de vraag. "
        + "Noem niets als feit als het niet uit de vraag of uit de opgehaalde context volgt. "
        + "Als de context niet voldoende is, zeg dat gewoon eerlijk.\n\n"
        + "Opgehaalde context:\n"
        + retrieved_context
    )


def _build_messages(
    identity_key: str,
    user_message: str,
    retrieved_context: str | None = None,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _system_prompt(identity_key, retrieved_context=retrieved_context)},
        {"role": "user", "content": user_message},
    ]


def _retryable_status(status_code: int) -> bool:
    return status_code in {429, 500, 502, 503, 504}


def _call_gemini(profile, messages: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.getenv(profile.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"API key ontbreekt voor profiel {profile.name} via env {profile.api_key_env}")

    system_parts = []
    user_parts = []

    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            user_parts.append(content)

    prompt = "\n\n".join(
        ([f"Systeeminstructie: {' '.join(system_parts)}"] if system_parts else [])
        + user_parts
    )

    client = genai.Client(api_key=api_key)

    last_error = None
    delays = [1, 2, 4]

    for attempt, delay in enumerate(delays, start=1):
        try:
            response = client.models.generate_content(
                model=profile.model,
                contents=prompt,
            )
            text = getattr(response, "text", "") or ""
            return {
                "provider": profile.provider,
                "profile": profile.name,
                "model": profile.model,
                "text": text,
            }
        except Exception as exc:
            last_error = exc
            status_code = getattr(exc, "status_code", None)

            if status_code is None and hasattr(exc, "response") and getattr(exc, "response") is not None:
                status_code = getattr(exc.response, "status_code", None)

            if status_code is not None and not _retryable_status(int(status_code)):
                raise

            if attempt == len(delays):
                break

            time.sleep(delay)

    raise RuntimeError(f"Gemini call mislukt na retries: {last_error}")


def generate_chat_response(
    identity_key: str,
    user_message: str,
    capability: str = "chat",
    retrieved_context: str | None = None,
) -> dict[str, Any]:
    profiles = resolve_profiles(identity_key=identity_key, capability=capability)
    if not profiles:
        raise RuntimeError("Geen actieve modelprofielen beschikbaar voor deze route")

    messages = _build_messages(
        identity_key=identity_key,
        user_message=user_message,
        retrieved_context=retrieved_context,
    )
    errors: list[str] = []

    for profile in profiles:
        try:
            if profile.provider == "google":
                result = _call_gemini(profile, messages)
            else:
                raise RuntimeError(f"provider nu niet actief voor deze route: {profile.provider}")

            result["identity_key"] = identity_key
            result["capability"] = capability
            return result

        except Exception as exc:
            errors.append(f"{profile.name}: {exc}")

    raise RuntimeError("Geen werkende providerroute gevonden | " + " | ".join(errors))
