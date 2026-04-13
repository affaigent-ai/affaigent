#!/usr/bin/env bash
set -euo pipefail

API_BASE="http://127.0.0.1:8000"

echo "== health =="
curl -fsS "$API_BASE/health"
echo
echo

echo "== create memory entry =="
CREATE_JSON=$(curl -fsS -X POST "$API_BASE/memory/entries" \
  -H 'Content-Type: application/json' \
  -d '{
    "identity_key": "dennis_work",
    "memory_type": "document_note",
    "title": "Smoke test memory",
    "content": "Affaigent gebruikt een lokale embedding service op de VPS en semantic search via Qdrant.",
    "summary": "Smoke test",
    "source_kind": "manual",
    "source_ref": "smoke-script",
    "importance": 3,
    "sensitivity": "normal",
    "metadata": {}
  }')

echo "$CREATE_JSON"
echo

MEMORY_ID=$(printf '%s' "$CREATE_JSON" | python3 -c 'import sys, json; print(json.load(sys.stdin)["memory_id"])')
echo "MEMORY_ID=$MEMORY_ID"
echo

echo "== chunk =="
curl -fsS -X POST "$API_BASE/memory/entries/$MEMORY_ID/chunk"
echo
echo

echo "== embed =="
curl -fsS -X POST "$API_BASE/memory/entries/$MEMORY_ID/embed"
echo
echo

echo "== semantic search =="
curl -fsS -X POST "$API_BASE/memory/search/semantic" \
  -H 'Content-Type: application/json' \
  -d '{
    "identity_key": "dennis_work",
    "query_text": "lokale embedding service op de VPS",
    "limit": 5
  }'
echo
echo

echo "== done =="
