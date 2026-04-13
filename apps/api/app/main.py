from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from psycopg.types.json import Jsonb

from app.config import settings
from app.db import get_db
from app.embeddings import get_embeddings, get_query_embedding
from app.model_router import explain_route
from app.llm import generate_chat_response
from app.chat_contexts import explain_chat_context
from app.chat_state import ensure_chat_context_state_table, get_chat_context_state, set_chat_context_state
from app.qdrant import ensure_collection, query_points, upsert_points
from app.schemas import (
    ChunkMemoryResponse,
    CreateMemoryEntryRequest,
    EmbedMemoryResponse,
    MemoryEntryListResponse,
    MemoryEntryResponse,
    ChatRespondRequest,
    ChatRespondResponse,
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)


def _validate_identity_key(identity_key: str) -> None:
    if identity_key not in settings.identities:
        raise HTTPException(status_code=400, detail="Invalid identity_key")


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)

    while start < text_length:
        end = min(text_length, start + chunk_size)
        chunk = normalized[start:end]

        if end < text_length:
            last_space = chunk.rfind(" ")
            if last_space > int(chunk_size * 0.6):
                end = start + last_space
                chunk = normalized[start:end]

        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_collection()
    ensure_chat_context_state_table()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }


@app.get("/contexts")
async def contexts() -> dict[str, list[str]]:
    return {
        "identities": list(settings.identities),
    }


@app.post("/memory/entries", response_model=MemoryEntryResponse)
async def create_memory_entry(payload: CreateMemoryEntryRequest) -> MemoryEntryResponse:
    memory_id = str(uuid4())

    query = """
    INSERT INTO memory_entries (
        memory_id,
        identity_key,
        memory_type,
        title,
        content,
        summary,
        source_kind,
        source_ref,
        source_event_at,
        importance,
        sensitivity,
        metadata
    )
    VALUES (
        %(memory_id)s,
        %(identity_key)s,
        %(memory_type)s,
        %(title)s,
        %(content)s,
        %(summary)s,
        %(source_kind)s,
        %(source_ref)s,
        %(source_event_at)s,
        %(importance)s,
        %(sensitivity)s,
        %(metadata)s
    )
    RETURNING
        memory_id,
        identity_key,
        connector_id,
        memory_type,
        title,
        content,
        summary,
        source_kind,
        source_ref,
        source_event_at,
        importance,
        sensitivity,
        status,
        metadata,
        created_at,
        updated_at
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "memory_id": memory_id,
                    "identity_key": payload.identity_key,
                    "memory_type": payload.memory_type,
                    "title": payload.title,
                    "content": payload.content,
                    "summary": payload.summary,
                    "source_kind": payload.source_kind,
                    "source_ref": payload.source_ref,
                    "source_event_at": payload.source_event_at,
                    "importance": payload.importance,
                    "sensitivity": payload.sensitivity,
                    "metadata": Jsonb(payload.metadata),
                },
            )
            row = cur.fetchone()

    return MemoryEntryResponse(**row)


@app.get("/memory/entries", response_model=MemoryEntryListResponse)
async def list_memory_entries(
    identity_key: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MemoryEntryListResponse:
    base_query = """
    SELECT
        memory_id,
        identity_key,
        connector_id,
        memory_type,
        title,
        content,
        summary,
        source_kind,
        source_ref,
        source_event_at,
        importance,
        sensitivity,
        status,
        metadata,
        created_at,
        updated_at
    FROM memory_entries
    """
    params: dict[str, object] = {"limit": limit, "offset": offset}

    if identity_key:
        _validate_identity_key(identity_key)
        base_query += " WHERE identity_key = %(identity_key)s"
        params["identity_key"] = identity_key

    base_query += " ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(base_query, params)
            rows = cur.fetchall()

    items = [MemoryEntryResponse(**row) for row in rows]
    return MemoryEntryListResponse(items=items, count=len(items))


@app.get("/memory/entries/{memory_id}", response_model=MemoryEntryResponse)
async def get_memory_entry(memory_id: str) -> MemoryEntryResponse:
    query = """
    SELECT
        memory_id,
        identity_key,
        connector_id,
        memory_type,
        title,
        content,
        summary,
        source_kind,
        source_ref,
        source_event_at,
        importance,
        sensitivity,
        status,
        metadata,
        created_at,
        updated_at
    FROM memory_entries
    WHERE memory_id = %(memory_id)s
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"memory_id": memory_id})
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Memory entry not found")

    return MemoryEntryResponse(**row)


@app.post("/memory/entries/{memory_id}/chunk", response_model=ChunkMemoryResponse)
async def chunk_memory_entry(memory_id: str) -> ChunkMemoryResponse:
    select_query = """
    SELECT
        memory_id,
        identity_key,
        connector_id,
        content
    FROM memory_entries
    WHERE memory_id = %(memory_id)s
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(select_query, {"memory_id": memory_id})
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Memory entry not found")

            chunks = _chunk_text(row["content"])
            if not chunks:
                raise HTTPException(
                    status_code=400,
                    detail="Memory entry content is empty after normalization",
                )

            cur.execute(
                "DELETE FROM memory_chunks WHERE memory_id = %(memory_id)s",
                {"memory_id": memory_id},
            )

            for idx, chunk_text in enumerate(chunks):
                cur.execute(
                    """
                    INSERT INTO memory_chunks (
                        chunk_id,
                        memory_id,
                        identity_key,
                        connector_id,
                        chunk_index,
                        chunk_text,
                        embedding_status,
                        metadata
                    )
                    VALUES (
                        %(chunk_id)s,
                        %(memory_id)s,
                        %(identity_key)s,
                        %(connector_id)s,
                        %(chunk_index)s,
                        %(chunk_text)s,
                        'pending',
                        %(metadata)s
                    )
                    """,
                    {
                        "chunk_id": str(uuid4()),
                        "memory_id": row["memory_id"],
                        "identity_key": row["identity_key"],
                        "connector_id": row["connector_id"],
                        "chunk_index": idx,
                        "chunk_text": chunk_text,
                        "metadata": Jsonb({}),
                    },
                )

    return ChunkMemoryResponse(
        memory_id=memory_id,
        chunks_created=len(chunks),
        status="ok",
    )


@app.post("/memory/entries/{memory_id}/embed", response_model=EmbedMemoryResponse)
async def embed_memory_entry(memory_id: str) -> EmbedMemoryResponse:
    query = """
    SELECT
        mc.chunk_id,
        mc.chunk_index,
        mc.chunk_text,
        mc.identity_key,
        mc.connector_id,
        me.memory_type,
        me.source_kind,
        me.sensitivity,
        me.status
    FROM memory_chunks mc
    JOIN memory_entries me ON me.memory_id = mc.memory_id
    WHERE mc.memory_id = %(memory_id)s
    ORDER BY mc.chunk_index ASC
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"memory_id": memory_id})
            rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No chunks found for memory entry")

    chunk_texts = [row["chunk_text"] for row in rows]

    try:
        vectors = get_embeddings(chunk_texts)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Embedding request failed: {exc}") from exc

    points = []
    for row, vector in zip(rows, vectors):
        payload = {
            "chunk_id": row["chunk_id"],
            "memory_id": memory_id,
            "identity_key": row["identity_key"],
            "connector_id": row["connector_id"],
            "chunk_index": row["chunk_index"],
            "memory_type": row["memory_type"],
            "source_kind": row["source_kind"],
            "sensitivity": row["sensitivity"],
            "status": row["status"],
        }
        points.append(
            {
                "id": row["chunk_id"],
                "vector": vector,
                "payload": payload,
            }
        )

    try:
        qdrant_result = upsert_points(points)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Qdrant upsert failed: {exc}") from exc

    with get_db() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    UPDATE memory_chunks
                    SET
                        embedding_status = 'embedded',
                        qdrant_point_id = %(qdrant_point_id)s,
                        updated_at = NOW()
                    WHERE chunk_id = %(chunk_id)s
                    """,
                    {
                        "qdrant_point_id": row["chunk_id"],
                        "chunk_id": row["chunk_id"],
                    },
                )

    return EmbedMemoryResponse(
        memory_id=memory_id,
        chunks_embedded=len(rows),
        qdrant_points_upserted=len(points),
        qdrant_status=qdrant_result.get("result", {}).get("status", "unknown"),
        status="ok",
    )


@app.post("/memory/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(payload: SemanticSearchRequest) -> SemanticSearchResponse:
    _validate_identity_key(payload.identity_key)

    try:
        query_vector = get_query_embedding(payload.query_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Query embedding failed: {exc}") from exc

    try:
        qdrant_result = query_points(
            query_vector=query_vector,
            identity_key=payload.identity_key,
            limit=payload.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Qdrant query failed: {exc}") from exc

    points = qdrant_result.get("result", {}).get("points", [])
    if not points:
        return SemanticSearchResponse(
            query_text=payload.query_text,
            identity_key=payload.identity_key,
            limit=payload.limit,
            hits=[],
            count=0,
        )

    chunk_ids = [
        point.get("payload", {}).get("chunk_id")
        for point in points
        if point.get("payload", {}).get("chunk_id")
    ]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    mc.chunk_id,
                    mc.memory_id,
                    mc.identity_key,
                    mc.chunk_index,
                    mc.chunk_text,
                    me.memory_type,
                    me.title,
                    me.summary,
                    me.source_kind,
                    me.sensitivity,
                    me.status
                FROM memory_chunks mc
                JOIN memory_entries me ON me.memory_id = mc.memory_id
                WHERE mc.chunk_id = ANY(%(chunk_ids)s)
                """,
                {"chunk_ids": chunk_ids},
            )
            rows = cur.fetchall()

    rows_by_chunk_id = {row["chunk_id"]: row for row in rows}

    hits: list[SemanticSearchHit] = []
    for point in points:
        point_payload = point.get("payload", {})
        chunk_id = point_payload.get("chunk_id")
        row = rows_by_chunk_id.get(chunk_id)
        if not row:
            continue

        hits.append(
            SemanticSearchHit(
                chunk_id=row["chunk_id"],
                memory_id=row["memory_id"],
                identity_key=row["identity_key"],
                chunk_index=row["chunk_index"],
                score=float(point.get("score", 0.0)),
                memory_type=row["memory_type"],
                title=row["title"],
                summary=row["summary"],
                source_kind=row["source_kind"],
                sensitivity=row["sensitivity"],
                status=row["status"],
                chunk_text=row["chunk_text"],
            )
        )

    return SemanticSearchResponse(
        query_text=payload.query_text,
        identity_key=payload.identity_key,
        limit=payload.limit,
        hits=hits,
        count=len(hits),
    )


def _build_retrieval_context(hits: list[SemanticSearchHit], max_chars: int = 3500) -> str:
    parts: list[str] = []
    total = 0

    for idx, hit in enumerate(hits, start=1):
        title = (hit.title or "").strip() or "zonder titel"
        summary = (hit.summary or "").strip()
        chunk_text = " ".join(hit.chunk_text.split()).strip()

        part_lines = [
            f"[Bron {idx}]",
            f"titel: {title}",
            f"memory_type: {hit.memory_type}",
            f"source_kind: {hit.source_kind}",
        ]

        if summary:
            part_lines.append(f"samenvatting: {summary}")

        part_lines.append(f"inhoud: {chunk_text}")
        part = "\n".join(part_lines)

        if total + len(part) > max_chars:
            remaining = max_chars - total
            if remaining <= 0:
                break
            part = part[:remaining].rstrip()
            if not part:
                break

        parts.append(part)
        total += len(part) + 2

        if total >= max_chars:
            break

    return "\n\n".join(parts)


@app.get("/model-route")
async def model_route(
    identity_key: str = Query(...),
    capability: str = Query(default="chat"),
) -> dict:
    _validate_identity_key(identity_key)
    return explain_route(identity_key=identity_key, capability=capability)


@app.get("/chat-context")
async def chat_context(
    chat_key: str = Query(...),
) -> dict:
    return explain_chat_context(chat_key=chat_key)


@app.get("/chat-context/current")
async def chat_context_current(
    chat_key: str = Query(...),
) -> dict:
    return get_chat_context_state(chat_key=chat_key)


@app.post("/chat-context/select")
async def chat_context_select(
    chat_key: str = Query(...),
    identity_key: str = Query(...),
) -> dict:
    _validate_identity_key(identity_key)
    return set_chat_context_state(chat_key=chat_key, identity_key=identity_key)


@app.post("/chat/respond", response_model=ChatRespondResponse)
async def chat_respond(payload: ChatRespondRequest) -> ChatRespondResponse:
    _validate_identity_key(payload.identity_key)

    retrieval_count = 0
    retrieved_context = None

    try:
        retrieval_result = await semantic_search(
            SemanticSearchRequest(
                query_text=payload.message,
                identity_key=payload.identity_key,
                limit=4,
            )
        )
        retrieval_count = retrieval_result.count
        if retrieval_result.hits:
            retrieved_context = _build_retrieval_context(retrieval_result.hits)
    except Exception:
        retrieval_count = 0
        retrieved_context = None

    try:
        result = generate_chat_response(
            identity_key=payload.identity_key,
            user_message=payload.message,
            capability=payload.capability,
            retrieved_context=retrieved_context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ChatRespondResponse(
        identity_key=result["identity_key"],
        capability=result["capability"],
        provider=result["provider"],
        profile=result["profile"],
        model=result["model"],
        reply=result["text"],
        retrieval_count=retrieval_count,
    )
