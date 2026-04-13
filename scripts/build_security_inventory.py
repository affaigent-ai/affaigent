#!/usr/bin/env python3
import json
from pathlib import Path

BASE = Path("/opt/affaigent")
STATUS_PATH = BASE / "logs/checks/latest_security_status.json"
OUT_JSON = BASE / "logs/checks/latest_security_inventory.json"
OUT_TXT = BASE / "logs/checks/latest_security_inventory.txt"

if not STATUS_PATH.exists():
    raise SystemExit(f"statusbestand ontbreekt: {STATUS_PATH}")

status = json.loads(STATUS_PATH.read_text())
source_summary = status.get("source_summary")
if not source_summary:
    raise SystemExit("source_summary ontbreekt in latest_security_status.json")

check_dir = Path(source_summary).parent
trivy_files = sorted(check_dir.glob("trivy_*.json"))

items = []

for trivy_file in trivy_files:
    try:
        data = json.loads(trivy_file.read_text() or "{}")
    except Exception:
        continue

    artifact = data.get("ArtifactName", trivy_file.name)

    for result in data.get("Results", []):
        target = result.get("Target")
        for vuln in result.get("Vulnerabilities", []) or []:
            sev = (vuln.get("Severity") or "").upper()
            if sev not in {"CRITICAL", "HIGH"}:
                continue

            items.append({
                "component": artifact,
                "severity": sev,
                "cve": vuln.get("VulnerabilityID"),
                "package": vuln.get("PkgName"),
                "installed_version": vuln.get("InstalledVersion"),
                "fixed_version": vuln.get("FixedVersion"),
                "status": "unreviewed",
                "target": target,
                "title": vuln.get("Title"),
            })

items.sort(key=lambda x: (x["severity"] != "CRITICAL", x["component"], x["cve"] or "", x["package"] or ""))

OUT_JSON.write_text(json.dumps(items, indent=2))

lines = []
lines.append("Affaigent security inventory")
lines.append(f"bronmap: {check_dir}")
lines.append("")

for item in items:
    lines.append(
        f"[{item['severity']}] {item['component']} | {item['cve']} | pkg={item['package']} | "
        f"installed={item['installed_version']} | fixed={item['fixed_version']} | target={item['target']} | status={item['status']}"
    )

OUT_TXT.write_text("\n".join(lines) + "\n")
print(OUT_TXT)
