"""Adaptive investment assistant research packet: deterministic facts, not trade signals.

Consumes the existing daily multi-market evidence. Distinguishes source failures,
large daily moves, stale data and unknown compliance from genuine approvals.
Public artifacts never contain holdings or account balances.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MARKETS = ("ABD", "BIST", "AVRUPA")
ALLOWED_STATUS = {"observed", "source_unavailable"}
MAX_DAILY_MOVE = 3.0
MAX_ROWS = 200


def parse_instant(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return stamp.astimezone(timezone.utc)


def evidence_packet(brief):
    if (not isinstance(brief, dict) or brief.get("schema_version") != 1
            or not isinstance(brief.get("markets"), dict)
            or set(brief["markets"]) != set(MARKETS)
            or brief.get("portfolio_positions_included") is not False):
        raise ValueError("incompatible or nonpublic source packet")
    created = parse_instant(brief["created_at"])
    output = {"schema_version": 1, "created_at": created.isoformat(),
              "research_only": True, "investment_decisions_generated": False,
              "personal_portfolio_included": False,
              "markets": {}, "work_queue": [], "quality": {}}
    seen = set()
    for market in MARKETS:
        market_rows = brief["markets"][market]
        if not isinstance(market_rows, list) or len(market_rows) > MAX_ROWS:
            raise ValueError("bounded public market universe required")
        rows = []
        for item in market_rows:
            symbol, status = item["symbol"], item["status"]
            if not isinstance(symbol, str) or not symbol or symbol in seen or status not in ALLOWED_STATUS:
                raise ValueError("invalid market symbol/status")
            seen.add(symbol)
            issue = []
            price = item.get("price")
            pct = item.get("change_1d_pct")
            when = item.get("market_at")
            if status == "source_unavailable":
                if price is not None or pct is not None or when is not None:
                    raise ValueError("missing source cannot contain observations")
                issue.append("missing_price_source")
            else:
                from math import isfinite
                if (type(price) not in (int, float) or not isfinite(price) or price <= 0
                        or not isinstance(when, str)):
                    raise ValueError("positive observed price and timestamp required")
                observed = parse_instant(when)
                seconds = (created - observed).total_seconds()
                if seconds < 0:
                    raise ValueError("future observation")
                if seconds > 4 * 86400:
                    issue.append("stale_price")
                if pct is not None:
                    if type(pct) not in (int, float) or not isfinite(pct) or abs(pct) > 10000:
                        raise ValueError("invalid daily return")
                    if abs(pct) >= MAX_DAILY_MOVE:
                        issue.append("large_price_move_requires_context")
            row = {"symbol": symbol, "market": market, "source_status": status,
                   "price": price, "currency": item.get("currency"),
                   "market_at": when, "change_1d_pct": pct,
                   "source_url": item.get("source_url"), "attention_reasons": issue,
                   "participation_status": "unknown",
                   "financial_health_status": "unreviewed",
                   "midas_tradability": "unverified",
                   "ai_research_status": "pending",
                   "investment_action": None, "score": None}
            rows.append(row)
            if issue:
                priority = 0 if "missing_price_source" in issue else 1 if "stale_price" in issue else 2
                output["work_queue"].append({"symbol": symbol, "market": market,
                                              "priority": priority, "reasons": issue})
        output["markets"][market] = rows
        output["quality"][market] = dict(Counter(r["source_status"] for r in rows))
    output["work_queue"].sort(key=lambda r: (r["priority"], r["market"], r["symbol"]))
    output["methodology"] = {
        "price_move_trigger_pct": MAX_DAILY_MOVE,
        "price_only_is_not_a_buy_or_sell_signal": True,
        "no_fabricated_compliance_or_financial_score": True,
        "ai_must_review_news_financials_and_market_context": True,
        "unverified_inputs_cannot_be_trade_approvals": True,
        "no_automatic_order": True,
    }
    return output


def analyst_prompt(packet):
    count = sum(len(x) for x in packet["markets"].values())
    queue = packet["work_queue"]
    lines = ["# Adaptif Yatırım Uzmanı | Günlük çalışma talimatı", "",
             f"Veri paketinin zamanı: {packet['created_at']}",
             f"İzlenen kamusal araştırma sembolü: {count}",
             f"Araştırma tetikleyicisi: {len(queue)}", "",
             "## Kesin çalışma sırası", "",
             "1. Önce kaynakların zamanını, eksik fiyatları ve hatalı kimlikleri kontrol et.",
             "2. ABD, BIST ve Avrupa için ayrı makro/piyasa yönü değerlendirmesi yap; kararsızlık geçerli sonuçtur.",
             "3. Kişisel portföy verilerini yalnızca güvenli kullanıcı kaynağından doğrula. Bu pakette yoktur.",
             "4. Önce portföydeki kritik şirket haberlerini, sonra yeni fırsatları araştır.",
             "5. Katılım uygunluğunu faaliyet ve finansal ölçütlerle bağımsız doğrula; bilinmiyorsa BEKLE/İNCELEME.",
             "6. Şirketin büyüme, borç, nakit akışı ve fiyatını sektöre uygun yöntemlerle değerlendir.",
             "7. Her AL/TUT/AZALT/SAT/BEKLE görüşünün karşıt kanıtını, senaryosunu ve güven düzeyini belirt.",
             "8. Kullanıcı işlem onayı vermeden emir verme. Sırf fiyat hareketinden öneri çıkarma.",
             "9. İşlem maliyeti, mevcut alternatifler ve nakitte kalma seçeneğini karşılaştır.",
             "10. Değişmeyen araştırmayı yeniden yazma; geçmiş sonuçları geleceği biliyormuş gibi düzeltme.",
             "11. Başarı veya hata iddiasını gerçekleşen sonuçlarla ve uygun kıyas endeksiyle doğrula.",
             "12. Gerçekleşmemiş analizleri tamamlandı olarak raporlama.", "",
             "## İlk araştırma sırası", ""]
    if not queue:
        lines.append("Fiyat değişimi veya kaynak sorunu tetikleyicisi yok; haber/bilanço olayları ayrıca taranmalı.")
    else:
        for r in queue[:30]:
            lines.append(f"- {r['market']} / {r['symbol']}: {', '.join(r['reasons'])}")
    lines.extend(["", "## Çıktı", "",
                  "Önce 'Bugün ne değişti?', ardından 'Portföy riskleri', 'Yeni fırsatlar',",
                  "'İşlem önerisi veya işlem yapmama gerekçesi', 'Eksik veriler' ve 'Karar günlüğü'.",
                  "Kaynak bağlantısı ve zaman vermeden yeni olgu iddia etme.",
                  "Kişisel portföy kayıtlarını bu kamusal GitHub deposuna gönderme.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", default="data/analyst-output/daily-brief.json")
    parser.add_argument("--output-dir", default="data/analyst-output")
    args = parser.parse_args()
    packet = evidence_packet(json.loads(Path(args.brief).read_text(encoding="utf-8")))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "research-packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "analyst-work-order.md").write_text(analyst_prompt(packet), encoding="utf-8")
    print(json.dumps({"tracked": sum(map(len, packet["markets"].values())),
                      "research_triggers": len(packet["work_queue"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
