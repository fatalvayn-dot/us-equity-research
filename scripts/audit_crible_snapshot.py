"""Report Crible-only data candidates without touching scored financial facts."""
import argparse
import json
from pathlib import Path
from equity_research.crible_audit import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crible-json", type=Path, required=True)
    parser.add_argument("--radar-html", type=Path, default=Path("docs/evidence/turkish-reports/finansal-rapor.html"))
    parser.add_argument("--output", type=Path, default=Path("crible-gap-audit.json"))
    args = parser.parse_args()
    result = audit(args.radar_html, args.crible_json)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"companies":result["companies"], "candidates":result["candidate_count"],
                     "accepted_facts":result["accepted_facts"], "fields":result["fields"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
