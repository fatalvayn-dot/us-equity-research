"""Daily Turkish research table for the five-issuer cohort, from scored evidence only.

Nothing here is an order or an investment approval. Target price is never invented:
the score model has no target-price component, so it is reported as 'hesaplanmadı'.
"""
import argparse
import json
from pathlib import Path

NOTE = ("Bu bir yatırım veya alım önerisi değildir. Katılım uygunluğu doğrulanmadığı için "
        "hiçbir şirkette AL görüşü verilemez; skor bir araştırma hipotezidir.")


def _cell(value, empty="—"):
    return empty if value in (None, "", []) else str(value).replace("|", "/")


def render(report):
    if not isinstance(report, dict) or not isinstance(report.get("companies"), list):
        raise ValueError("scored five-company report required")
    rows = []
    for c in report["companies"]:
        alt = c.get("alternate_definitions") or []
        alt_text = ", ".join(a["required_field"] + "→" + a["used_field"] for a in alt) or "yok"
        scored = c.get("score") is not None
        rows.append("| " + " | ".join([
            _cell(c.get("symbol")), _cell(c.get("latest_daily_close")), _cell(c.get("price_as_of")),
            _cell(c.get("score")) if scored else "puansız",
            _cell(c.get("score_status")), alt_text, "hesaplanmadı",
            _cell(", ".join(c.get("blockers", [])[:3]))]) + " |")
    scored_n = sum(c.get("score") is not None for c in report["companies"])
    lines = ["# ABD 5 şirket günlük araştırma tablosu", "",
             "Skorlu: %d/%d · Katılım ve alım onayı: YOK" % (scored_n, len(report["companies"])), "",
             "| Sembol | Son kapanış | Fiyat tarihi | Skor | Skor durumu | Alternatif tanım | Hedef fiyat | Engeller |",
             "|---|---|---|---|---|---|---|---|", *rows, "",
             "Alternatif tanım: zorunlu GAAP kavramı yayımlanmadığında v3 modelinin etiketli, eşdeğer olmayan yedeği.",
             "Hedef fiyat: skor modelinde hedef fiyat bileşeni yok; uydurulmaz.", "", NOTE, ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", required=True);ap.add_argument("--out")
    args = ap.parse_args(argv)
    text = render(json.loads(Path(args.scored).read_text(encoding="utf-8")))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
