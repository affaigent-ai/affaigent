#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime

CHECKS_DIR = Path("/opt/affaigent/logs/checks")


def parse_summary(summary_path: Path) -> dict:
    text = summary_path.read_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    components = {}
    current = None

    for line in lines:
        if line.startswith("--- ") and line.endswith(" ---"):
            current = line[4:-4].strip()
            continue

        if current and ": CRITICAL=" in line and ", HIGH=" in line:
            # voorbeeld:
            # postgres:16.13: CRITICAL=1, HIGH=8
            try:
                _, counts = line.split(": CRITICAL=", 1)
                critical_str, high_str = counts.split(", HIGH=", 1)
                critical = int(critical_str.strip())
                high = int(high_str.strip())
                components[current] = {
                    "critical": critical,
                    "high": high,
                }
            except Exception:
                pass

    python_status = "unknown"
    if "python dependencies: geen bekende kwetsbaarheden" in text:
        python_status = "ok"
    elif "python dependencies:" in text:
        python_status = "check_needed"

    total_critical = sum(v["critical"] for v in components.values())
    total_high = sum(v["high"] for v in components.values())

    if total_critical > 0:
        overall = "red"
        advice = "kritieke kwetsbaarheden gevonden; triage en actievoorstel nodig"
    elif total_high >= 10:
        overall = "orange"
        advice = "meerdere hoge kwetsbaarheden; bundelen in actieplan"
    elif total_high > 0:
        overall = "yellow"
        advice = "beperkte hoge kwetsbaarheden; meenemen in onderhoud"
    else:
        overall = "green"
        advice = "geen hoge of kritieke kwetsbaarheden gevonden"

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_summary": str(summary_path),
        "overall_status": overall,
        "advice": advice,
        "totals": {
            "critical": total_critical,
            "high": total_high,
        },
        "python_dependencies": python_status,
        "components": components,
    }


def build_human_summary(status: dict) -> str:
    lines = []
    lines.append("Affaigent security status")
    lines.append(f"tijd: {status['generated_at']}")
    lines.append(f"status: {status['overall_status']}")
    lines.append(f"advies: {status['advice']}")
    lines.append(
        f"totaal: CRITICAL={status['totals']['critical']}, HIGH={status['totals']['high']}"
    )
    lines.append(f"python dependencies: {status['python_dependencies']}")
    lines.append("")
    lines.append("componenten:")
    for name, counts in status["components"].items():
        lines.append(
            f"- {name}: CRITICAL={counts['critical']}, HIGH={counts['high']}"
        )
    lines.append("")
    lines.append(f"bron: {status['source_summary']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not CHECKS_DIR.exists():
        print("checks dir bestaat niet", file=sys.stderr)
        return 1

    runs = sorted([p for p in CHECKS_DIR.iterdir() if p.is_dir()], reverse=True)
    if not runs:
        print("geen checkruns gevonden", file=sys.stderr)
        return 1

    latest = runs[0]
    summary_path = latest / "summary.txt"
    if not summary_path.exists():
        print("summary.txt ontbreekt", file=sys.stderr)
        return 1

    status = parse_summary(summary_path)

    status_path = latest / "security_status.json"
    human_path = latest / "security_summary.txt"
    latest_json = CHECKS_DIR / "latest_security_status.json"
    latest_txt = CHECKS_DIR / "latest_security_summary.txt"

    status_path.write_text(json.dumps(status, indent=2) + "\n")
    human_path.write_text(build_human_summary(status))
    latest_json.write_text(json.dumps(status, indent=2) + "\n")
    latest_txt.write_text(build_human_summary(status))

    print(f"status geschreven: {status_path}")
    print(f"samenvatting geschreven: {human_path}")
    print(f"latest json: {latest_json}")
    print(f"latest txt: {latest_txt}")
    print(f"overall_status={status['overall_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
