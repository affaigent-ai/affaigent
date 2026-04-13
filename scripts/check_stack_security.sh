#!/usr/bin/env bash
set -euo pipefail

STAMP=$(date +%F-%H%M%S)
OUTDIR="/opt/affaigent/logs/checks/$STAMP"
TRIVY_CACHE="/opt/affaigent/data/trivy-cache"
mkdir -p "$OUTDIR" "$TRIVY_CACHE"

IMAGES=(
  "docker-api:latest"
  "postgres:16.13"
  "redis:7.4.8-alpine"
  "qdrant/qdrant:v1.16.3"
  "ghcr.io/huggingface/text-embeddings-inference:cpu-1.9"
)

echo "== Affaigent stack security check ==" | tee "$OUTDIR/summary.txt"
echo "tijd: $(date -Iseconds)" | tee -a "$OUTDIR/summary.txt"
echo | tee -a "$OUTDIR/summary.txt"

echo "== versie-overzicht ==" | tee -a "$OUTDIR/summary.txt"
docker compose -f /opt/affaigent/infra/docker/docker-compose.yml ps | tee "$OUTDIR/compose_ps.txt" | tee -a "$OUTDIR/summary.txt" >/dev/null
echo | tee -a "$OUTDIR/summary.txt"

echo "== Trivy image scans ==" | tee -a "$OUTDIR/summary.txt"

for image in "${IMAGES[@]}"; do
  safe_name=$(echo "$image" | tr '/:' '__')
  json_report="$OUTDIR/trivy_$safe_name.json"

  echo "--- $image ---" | tee -a "$OUTDIR/summary.txt"

  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$TRIVY_CACHE:/root/.cache/trivy" \
    aquasec/trivy:0.68.2 \
    image \
    --skip-version-check \
    --scanners vuln \
    --severity HIGH,CRITICAL \
    --ignore-unfixed \
    --format json \
    "$image" > "$json_report" || true

  python3 - "$json_report" "$image" <<'PY' | tee -a "$OUTDIR/summary.txt"
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
image = sys.argv[2]

high = 0
critical = 0

try:
    data = json.loads(report_path.read_text() or "{}")
except Exception:
    print(f"{image}: rapport niet leesbaar")
    raise SystemExit(0)

for result in data.get("Results", []):
    for vuln in result.get("Vulnerabilities", []) or []:
        sev = (vuln.get("Severity") or "").upper()
        if sev == "HIGH":
            high += 1
        elif sev == "CRITICAL":
            critical += 1

print(f"{image}: CRITICAL={critical}, HIGH={high}")
PY

  echo | tee -a "$OUTDIR/summary.txt"
done

echo "== Python dependency scan ==" | tee -a "$OUTDIR/summary.txt"
docker run --rm \
  -v /opt/affaigent/apps/api:/src \
  -w /src \
  python:3.12-slim \
  sh -lc "pip install --no-cache-dir pip-audit >/dev/null && pip-audit -r requirements.txt" \
  > "$OUTDIR/pip_audit.txt" 2>&1 || true

python3 - "$OUTDIR/pip_audit.txt" <<'PY' | tee -a "$OUTDIR/summary.txt"
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text()

if "No known vulnerabilities found" in text:
    print("python dependencies: geen bekende kwetsbaarheden")
else:
    print(f"python dependencies: controleer {p}")
PY

echo | tee -a "$OUTDIR/summary.txt"
echo "klaar: $OUTDIR" | tee -a "$OUTDIR/summary.txt"
/opt/affaigent/scripts/build_security_status.py >/dev/null
python3 /opt/affaigent/scripts/build_security_inventory.py >/dev/null
python3 /opt/affaigent/scripts/build_security_reviewed_inventory.py >/dev/null
python3 /opt/affaigent/scripts/build_security_decision.py >/dev/null
python3 /opt/affaigent/scripts/build_security_notification.py >/dev/null
python3 /opt/affaigent/scripts/send_security_notification.py >/dev/null
