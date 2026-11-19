"""Render an existing dated research-score archive as unsigned Turkish report.

Offline only. Example:
  PYTHONPATH=src python scripts/export_decision_report.py \
    --score-report docs/evidence/current-score100/report.json.gz \
    --output /tmp/karar-arastirmasi.md

The optional --participation JSON is a list of the Stage-6 *research* outcomes
with the exact issuer identity. It never creates eligibility or buy decisions.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from equity_research.decision_report import build_decision_report, render_decision_markdown


def load_json(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw), hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--score-report", type=Path, required=True)
    p.add_argument("--participation", type=Path, help="optional noncertifying stage-6 results JSON")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    scored, original_sha = load_json(args.score_report)
    supplied = None
    participation_sha = None
    if args.participation is not None:
        supplied, participation_sha = load_json(args.participation)
    result = build_decision_report(scored, supplied)
    text = render_decision_markdown(result)

    input_paths = [args.score_report]
    if args.participation is not None:
        input_paths.append(args.participation)
    output = args.output.resolve()
    if output in {p.resolve() for p in input_paths}:
        raise ValueError("cannot overwrite source evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(json.dumps({
        "status": "offline_presentation_only",
        "score_source_sha256": original_sha,
        "participation_source_sha256": participation_sha,
        "original_cutoff": result["orijinal_kaynak_kesimi"],
        "candidates": result["aday_sayisi"],
        "numeric_research_scores": result["puanli_sirket"],
        "approved_investments": 0,
        "new_network_requests": 0,
        "recommendations_generated": 0,
        "output": str(output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
