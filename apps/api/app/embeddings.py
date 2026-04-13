import httpx

from app.config import settings


def _normalize_text(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        raise RuntimeError("One or more texts are empty after normalization")
    return normalized


def _embed_inputs(inputs: list[str]) -> list[list[float]]:
    url = f"{settings.embedding_base_url.rstrip('/')}/embed"

    response = httpx.post(
        url,
        headers={"Content-Type": "application/json"},
        json={"inputs": inputs},
        timeout=120.0,
    )
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected embedding response type: {type(data).__name__}")

    if len(data) != len(inputs):
        raise RuntimeError(
            f"Embedding count mismatch: expected {len(inputs)}, got {len(data)}"
        )

    vectors: list[list[float]] = []
    for idx, vector in enumerate(data):
        if not isinstance(vector, list):
            raise RuntimeError(f"Embedding at index {idx} is not a list")
        if len(vector) != settings.memory_vector_size:
            raise RuntimeError(
                f"Embedding at index {idx} has length {len(vector)}; "
                f"expected {settings.memory_vector_size}"
            )
        vectors.append(vector)

    return vectors


def get_embeddings(texts: list[str]) -> list[list[float]]:
    cleaned = [_normalize_text(text) for text in texts]
    prefixed = [f"passage: {text}" for text in cleaned]
    return _embed_inputs(prefixed)


def get_query_embedding(text: str) -> list[float]:
    cleaned = _normalize_text(text)
    return _embed_inputs([f"query: {cleaned}"])[0]
