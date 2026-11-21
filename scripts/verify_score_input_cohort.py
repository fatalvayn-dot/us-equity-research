"""Fail closed unless financial and valuation artifacts describe one cohort."""
import argparse
import json
from pathlib import Path


def _identities(rows, label):
    identities = []
    for row in rows:
        cik = row.get("issuer_id")
        symbol = row.get("symbol")
        if not isinstance(cik, str) or not cik.isdecimal() or len(cik) != 10:
            raise ValueError(f"{label} geçersiz CIK içeriyor")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"{label} geçersiz sembol içeriyor")
        identities.append((cik, symbol))
    if len(set(identities)) != len(identities):
        raise ValueError(f"{label} yinelenen şirket kimliği içeriyor")
    return set(identities)


def verify(financial, valuation):
    financial_ids = _identities(financial.get("companies", []), "Finansal paket")
    valuation_ids = _identities(valuation.get("companies", []), "Değerleme paketi")
    if not financial_ids or financial_ids != valuation_ids:
        missing = sorted(financial_ids - valuation_ids)
        extra = sorted(valuation_ids - financial_ids)
        raise ValueError(
            "Finansal ve değerleme kohortu uyuşmuyor: "
            f"finansal={len(financial_ids)}, değerleme={len(valuation_ids)}, "
            f"değerlemede_eksik={len(missing)}, değerlemede_fazla={len(extra)}"
        )
    return {"companies": len(financial_ids), "cohort_match": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--financial", type=Path, required=True)
    parser.add_argument("--valuation", type=Path, required=True)
    args = parser.parse_args()
    result = verify(json.loads(args.financial.read_text()),
                    json.loads(args.valuation.read_text()))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
