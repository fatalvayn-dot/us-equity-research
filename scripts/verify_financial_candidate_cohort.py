"""Fail closed when valuation candidates differ from their financial source cohort."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.verify_score_input_cohort import _identities


def verify(financial, candidates, *, financial_bytes=b"", candidate_bytes=b""):
    financial_ids = _identities(financial.get("companies", []), "Finansal paket")
    candidate_ids = _identities(candidates.get("companies", []), "Aday listesi")
    if not candidate_ids or financial_ids != candidate_ids:
        financial_only = sorted(financial_ids - candidate_ids)
        candidates_only = sorted(candidate_ids - financial_ids)
        detail = (
            f"finansal={len(financial_ids)}, aday={len(candidate_ids)}, "
            f"finansalda_fazla={len(financial_only)}, adayda_eksik={len(candidates_only)}, "
            f"finansal_fazla_semboller={','.join(x[1] for x in financial_only[:20])}, "
            f"adayda_eksik_semboller={','.join(x[1] for x in candidates_only[:20])}"
        )
        raise ValueError("Finansal kaynak ve değerleme aday kohortu uyuşmuyor: " + detail)
    return {
        "companies": len(financial_ids),
        "cohort_match": True,
        "financial_sha256": hashlib.sha256(financial_bytes).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--financial", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    args = parser.parse_args()
    financial_bytes = args.financial.read_bytes()
    candidate_bytes = args.candidates.read_bytes()
    result = verify(
        json.loads(financial_bytes),
        json.loads(candidate_bytes),
        financial_bytes=financial_bytes,
        candidate_bytes=candidate_bytes,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
