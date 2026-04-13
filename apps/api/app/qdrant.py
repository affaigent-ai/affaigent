import httpx

from app.config import settings


QDRANT_INDEX_FIELDS = (
    "identity_key",
    "connector_id",
    "memory_id",
    "memory_type",
    "source_kind",
    "sensitivity",
    "status",
)


def _base_url() -> str:
    return f"http://{settings.qdrant_host}:{settings.qdrant_http_port}"


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key
    return headers


def ensure_collection() -> dict:
    collection_url = f"{_base_url()}/collections/{settings.qdrant_memory_collection}"
    created = False

    with httpx.Client(timeout=120.0) as client:
        response = client.get(collection_url, headers=_headers())

        if response.status_code == 404:
            create_response = client.put(
                collection_url,
                headers=_headers(),
                json={
                    "vectors": {
                        "size": settings.memory_vector_size,
                        "distance": "Cosine",
                    }
                },
            )
            create_response.raise_for_status()
            created = True
        else:
            response.raise_for_status()
            data = response.json()
            vectors = data["result"]["config"]["params"]["vectors"]
            actual_size = vectors.get("size") if isinstance(vectors, dict) else None
            if actual_size is not None and actual_size != settings.memory_vector_size:
                raise RuntimeError(
                    f"Qdrant collection `{settings.qdrant_memory_collection}` has "
                    f"vector size {actual_size}, expected {settings.memory_vector_size}"
                )

        for field in QDRANT_INDEX_FIELDS:
            index_response = client.put(
                f"{collection_url}/index?wait=true",
                headers=_headers(),
                json={
                    "field_name": field,
                    "field_schema": "keyword",
                },
            )
            index_response.raise_for_status()

    return {
        "collection": settings.qdrant_memory_collection,
        "created": created,
        "indexes": list(QDRANT_INDEX_FIELDS),
    }


def upsert_points(points: list[dict]) -> dict:
    url = (
        f"{_base_url()}/collections/"
        f"{settings.qdrant_memory_collection}/points?wait=true"
    )

    response = httpx.put(
        url,
        headers=_headers(),
        json={"points": points},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


def query_points(
    query_vector: list[float],
    identity_key: str,
    limit: int,
) -> dict:
    url = (
        f"{_base_url()}/collections/"
        f"{settings.qdrant_memory_collection}/points/query"
    )

    response = httpx.post(
        url,
        headers=_headers(),
        json={
            "query": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
            "filter": {
                "must": [
                    {
                        "key": "identity_key",
                        "match": {"value": identity_key},
                    }
                ]
            },
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()
