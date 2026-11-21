"""Bounded scheduled radar workers; no trading, private portfolio or paid model."""
from __future__ import annotations

import argparse
import json
import pathlib
import tempfile
from datetime import date, datetime, timezone

from scripts import market_radar_pilot as pilot

MAX_LEDGER_BYTES = 8_000_000


def read_jsonl(filename):
    path = pathlib.Path(filename)
    if not path.exists():
        return []
    if path.stat().st_size > MAX_LEDGER_BYTES:
        raise ValueError("ledger size limit exceeded")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("invalid ledger item")
            rows.append(item)
    return rows


def write_jsonl(filename, rows):
    pathlib.Path(filename).write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8")


def identity(row):
    return (row.get("symbol"), row.get("as_of"))


def process(raw, previous, evaluations):
    """Append-only: retain earlier observations, add new daily signals and outcomes."""
    now = datetime.fromisoformat(raw["generated_at_utc"].replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("generation timestamp must include timezone")
    seen = {identity(p) for p in previous}
    assessed = {identity(e) for e in evaluations}
    new_predictions, new_evaluations, warnings = [], [], []
    is_live = raw.get("mode") == "live_attempt"
    for f in raw.get("forecasts", []):
        if not is_live or f.get("source") not in ("yfinance_daily", "yahoo_chart_daily", "stooq_daily"):
            continue
        key = identity(f)
        if not all(key) or key in seen:
            continue
        try:
            days_old = (now.date() - date.fromisoformat(f["as_of"])).days
        except (ValueError, TypeError, KeyError):
            warnings.append("invalid_date")
            continue
        if not 0 <= days_old <= 7:
            warnings.append("stale_or_future:" + str(f.get("symbol")))
            continue
        if (f.get("direction") not in ("yukari", "asagi", "kararsiz")
                or f.get("eligibility") != "bilinmiyor"
                or f.get("investment_advice") is not False):
            warnings.append("research_permission_gate:" + str(f.get("symbol")))
            continue
        new_predictions.append({
            "symbol": key[0], "as_of": key[1], "direction": f["direction"],
            "method": f.get("method"), "horizon_sessions": 5,
            "source": f["source"], "close": f["close"],
            "observed_at_utc": now.isoformat(), "confidence": None,
            "eligibility": "bilinmiyor", "investment_advice": False,
        })
        seen.add(key)

    previous_by_key = {identity(p): p for p in previous}
    for outcome in raw.get("evaluation", []):
        key = identity(outcome)
        if (outcome.get("status") != "evaluated" or key in assessed
                or key not in previous_by_key):
            continue
        if outcome.get("actual") not in ("yukari", "asagi", "duz"):
            warnings.append("invalid_outcome")
            continue
        new_evaluations.append({
            "symbol": key[0], "as_of": key[1],
            "method": previous_by_key[key].get("method"),
            "actual": outcome["actual"], "realized_5d": outcome["realized_5d"],
            "hit": outcome.get("hit"), "evaluated_at_utc": now.isoformat(),
        })
        assessed.add(key)

    full_predictions = previous + new_predictions
    full_evaluations = evaluations + new_evaluations
    hits = [e["hit"] for e in full_evaluations if isinstance(e.get("hit"), bool)]
    count = len(raw.get("forecasts", []))
    status = "ok" if count and not raw.get("errors") and not warnings else ("kismi" if count else "canli_veri_yok")
    if not is_live:
        status = "test_verisi"
    return ({
        "generated_at_utc": now.isoformat(), "status": status, "mode": raw.get("mode"),
        "agents": {
            "proje_muduru": "tamamlandi", "veri": "canli_deneme" if is_live else "fixture",
            "tahmin": "referans_sinyal" if count else "bekliyor",
            "haber": raw.get("news", {}).get("status", "bilinmiyor"),
            "gerceklesme_denetimi": "tamamlandi",
            "kalite_denetimi": "tamamlandi", "raporlama": "tamamlandi",
        },
        "current_forecasts": count, "new_predictions": len(new_predictions),
        "total_predictions": len(full_predictions),
        "new_evaluations": len(new_evaluations),
        "total_evaluations": len(full_evaluations),
        "direction_hit_rate": round(sum(hits) / len(hits), 4) if hits else None,
        "direction_hit_sample": len(hits),
        "errors": raw.get("errors", []), "warnings": warnings,
        "coverage": raw.get("coverage", {}),
        "restrictions": {
            "orders": False, "portfolio_access": False,
            "participation_approval": False, "trading_recommendations": False,
            "llm_agents_enabled": False,
        },
    }, full_predictions, full_evaluations)


def turkish_report(s):
    hit = ("Henüz ölçülemedi" if s["direction_hit_rate"] is None
           else "%" + str(round(100 * s["direction_hit_rate"], 1))
           + " (örnek " + str(s["direction_hit_sample"]) + ")")
    return (
        "# Piyasa radarı — zamanlanmış araştırma\n\n"
        + "- UTC zamanı: " + s["generated_at_utc"] + "\n"
        + "- Durum: " + s["status"] + "; kaynak kipi: " + str(s["mode"]) + "\n"
        + "- Bu oturumdaki sinyal: " + str(s["current_forecasts"]) + "\n"
        + "- Yeni tahmin: " + str(s["new_predictions"]) + "; toplam: " + str(s["total_predictions"]) + "\n"
        + "- Yeni gerçekleşme: " + str(s["new_evaluations"]) + "; toplam: " + str(s["total_evaluations"]) + "\n"
        + "- Geçmiş yön isabeti: " + hit + "\n"
        + "- Veri hatası: " + str(len(s["errors"])) + "; denetim uyarısı: " + str(len(s["warnings"])) + "\n\n"
        + "Yalnız araştırma; kalibre edilmemiş momentum. Katılım uygunluğu teyit edilmedi. "
        + "Gerçek emir, portföy erişimi, yatırım önerisi ve kendi kendini eğiten model yok.\n"
    )


def execute(outdir, prior_path, eval_path, fixture=None, rss=None, universe=None):
    output = pathlib.Path(outdir)
    output.mkdir(parents=True, exist_ok=True)
    prior, old_evals = read_jsonl(prior_path), read_jsonl(eval_path)
    evaluated_keys = {identity(e) for e in old_evals}
    pending = [
        {"symbol": p["symbol"], "as_of": p["as_of"], "direction": p["direction"]}
        for p in prior if identity(p) not in evaluated_keys
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "pending.json"
        path.write_text(json.dumps(pending), encoding="utf-8")
        raw = pilot.run(fixture=fixture, prior=str(path), feed=rss, universe=universe)
    summary, predictions, outcomes = process(raw, prior, old_evals)
    write_jsonl(output / "predictions.jsonl", predictions)
    write_jsonl(output / "evaluations.jsonl", outcomes)
    (output / "latest.json").write_text(
        json.dumps({"summary": summary, "research": raw}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (output / "latest.md").write_text(turkish_report(summary), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="radar-output")
    parser.add_argument("--predictions", default="radar-input/predictions.jsonl")
    parser.add_argument("--evaluations", default="radar-input/evaluations.jsonl")
    parser.add_argument("--fixture")
    parser.add_argument("--rss")
    parser.add_argument("--universe", help="Public research list for observation only")
    args = parser.parse_args()
    summary = execute(args.output, args.predictions, args.evaluations, args.fixture, args.rss, args.universe)
    print(json.dumps({"status": summary["status"], "signals": summary["current_forecasts"],
                      "new_predictions": summary["new_predictions"],
                      "new_evaluations": summary["new_evaluations"]}, ensure_ascii=False))
    return 2 if summary["status"] == "canli_veri_yok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
