from dataclasses import asdict

from app.config import ModelProfile, settings


def _profile_map() -> dict[str, ModelProfile]:
    return {profile.name: profile for profile in settings.model_profiles}


def get_route_names(identity_key: str, capability: str) -> list[str]:
    routes: dict[tuple[str, str], list[str]] = {
        ("dennis_work", "chat"): ["gemini_primary", "local_fallback"],
        ("dennis_private", "chat"): ["gemini_primary", "local_fallback"],
        ("linsey_work", "chat"): ["openai_primary", "gemini_primary", "local_fallback"],
        ("linsey_private", "chat"): ["openai_primary", "gemini_primary", "local_fallback"],
        ("shared_private", "chat"): ["gemini_primary", "local_fallback"],

        ("dennis_work", "planner"): ["gemini_primary", "local_fallback"],
        ("dennis_private", "planner"): ["gemini_primary", "local_fallback"],
        ("linsey_work", "planner"): ["openai_primary", "gemini_primary", "local_fallback"],
        ("linsey_private", "planner"): ["openai_primary", "gemini_primary", "local_fallback"],
        ("shared_private", "planner"): ["gemini_primary", "local_fallback"],

        ("dennis_work", "fast"): ["gemini_primary", "local_fallback"],
        ("dennis_private", "fast"): ["gemini_primary", "local_fallback"],
        ("linsey_work", "fast"): ["gemini_primary", "openai_primary", "local_fallback"],
        ("linsey_private", "fast"): ["gemini_primary", "openai_primary", "local_fallback"],
        ("shared_private", "fast"): ["gemini_primary", "local_fallback"],
    }

    return routes.get((identity_key, capability), ["openai_primary", "local_fallback"])


def resolve_profiles(identity_key: str, capability: str) -> list[ModelProfile]:
    profile_map = _profile_map()
    ordered_names = get_route_names(identity_key, capability)

    resolved: list[ModelProfile] = []
    for name in ordered_names:
        profile = profile_map.get(name)
        if not profile:
            continue
        if not profile.enabled:
            continue
        resolved.append(profile)

    return resolved


def explain_route(identity_key: str, capability: str) -> dict:
    profiles = resolve_profiles(identity_key, capability)
    return {
        "identity_key": identity_key,
        "capability": capability,
        "profiles": [asdict(profile) for profile in profiles],
        "count": len(profiles),
    }
