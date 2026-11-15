"""Compact public evidence handoff for an analyst; no decisions, no personal data."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path("data/analyst-output")
MARKETS = ("ABD", "BIST", "AVRUPA")


def parse_dt(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError("naive timestamp")
    return stamp.astimezone(timezone.utc)


def build_handoff(brief, packet, multi):
    if any(not isinstance(x, dict) or x.get("schema_version") != 1 for x in (brief, packet, multi)):
        raise ValueError("source schema mismatch")
    if (brief.get("portfolio_positions_included") is not False
            or packet.get("personal_portfolio_included") is not False
            or multi.get("personal_portfolio_included") is not False):
        raise ValueError("private data source rejected")
    if (set(brief.get("markets", {})) != set(MARKETS)
            or set(packet.get("markets", {})) != set(MARKETS)):
        raise ValueError("market coverage mismatch")
    created = [parse_dt(x["created_at"]) for x in (brief, packet, multi)]
    if max(created) - min(created) > timedelta(minutes=30):
        raise ValueError("mixed-day evidence")
    seen = set()
    markets = {}
    for name in MARKETS:
        rows = packet["markets"][name]
        observed = []
        incomplete = []
        for r in rows:
            symbol = r["symbol"]
            if symbol in seen or not isinstance(symbol, str):
                raise ValueError("duplicate/invalid symbol")
            seen.add(symbol)
            if r["source_status"] == "observed":
                observed.append(r)
            else:
                incomplete.append(symbol)
        markets[name] = {
            "tracked": len(rows), "observed": len(observed), "missing": incomplete,
            "latest_observation_utc": max((r["market_at"] for r in observed), default=None)
        }
    return {
        "schema_version": 1,
        "purpose": "public_research_only_not_an_investment_decision",
        "generated_at_utc": max(created).isoformat(),
        "source_created_at_utc": [x.isoformat() for x in created],
        "market_quality": markets,
        "research_queue": packet.get("work_queue", [])[:30],
        "supplemental_instruments": len(multi["instruments"]),
        "portfolio_data_present": False,
        "participation_verified": False,
        "investment_decision_present": False,
        "work_result_included": False,
        "next_analyst_steps": [
            "Check source timestamps, missing quotes and stale price observations",
            "Open latest Work research report separately; this packet cannot prove it ran",
            "Check geopolitical and macro changes using dated independent sources",
            "Check participation business and financial screens, including borderline ratios",
            "Privately verify user's real positions, not in public GitHub",
            "Evaluate independent paper portfolio with no retroactive fills",
            "Write a dated thesis and counter-thesis before any decision"
        ]
    }


def main():
    brief = json.loads((ROOT / "daily-brief.json").read_text(encoding="utf-8"))
    packet = json.loads((ROOT / "research-packet.json").read_text(encoding="utf-8"))
    multi = json.loads((ROOT / "multiactive-research.json").read_text(encoding="utf-8"))
    output = build_handoff(brief, packet, multi)
    (ROOT / "analyst-handoff.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Analist veri devri", "", f"Kaynak zamanı: {output['generated_at_utc']}", "",
             "Bu paket yatırım kararı, katılım uygunluğu veya GPT Work teslimatı değildir.", "",
             "| Piyasa | İzlenen | Fiyatlı | Eksik | Son piyasa zaman damgası |",
             "|---|---:|---:|---:|---|"]
    for name, m in output["market_quality"].items():
        lines.append(f"| {name} | {m['tracked']} | {m['observed']} | {len(m['missing'])} | {m['latest_observation_utc'] or 'Yok'} |")
    lines.extend(["", f"İnceleme tetikleyicisi: {len(output['research_queue'])}", "",
                  "Work raporu ayrıca okunmalı; bu devrin tamamlanması yatırım asistanının "
                  "otomatik analiz yaptığı anlamına gelmez.", ""])
    (ROOT / "analyst-handoff.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"markets": output["market_quality"],
                      "research_queue": len(output["research_queue"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
