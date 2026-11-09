"""Bind a published score to its exact production input files and run IDs."""
import argparse
import json
import os
from pathlib import Path

from scripts.live_checkpoint import digest


def write(data: Path, *, score_run: int, valuation_run: int, financial_run: int,
          commit: str) -> dict:
    if any(type(run) is not int or run <= 0 for run in (score_run, valuation_run, financial_run)):
        raise ValueError("Skor ve kaynak run ID değerleri pozitif olmalıdır")
    valuation = data / "valuation"
    work = data / "first-score-work"
    marker = json.loads((valuation / "financial-source-run.json").read_text())
    if type(marker["run_id"]) is not int or marker["run_id"] != financial_run:
        raise ValueError("Değerleme ve finansal kaynak run ID değerleri uyuşmuyor")

    market_manifest = valuation / "source-bundle/manifest.json"
    finance_manifest = data / "financial-evidence/live-sources/manifest.json"
    output_manifest = work / "output/manifest.json"
    report = json.loads(output_manifest.read_text())
    market_sha = digest(market_manifest)
    finance_sha = digest(finance_manifest)
    if (report["source_bundle_manifest_sha256"] != market_sha
            or [entry["manifest_sha256"] for entry in report["additional_financial_source_bundles"]]
            != [finance_sha]):
        raise ValueError("Skor ve kaynak paket özetleri uyuşmuyor")

    record = {
        "schema_version": 1,
        "score_run_id": score_run,
        "repository_commit": commit,
        "valuation_run_id": valuation_run,
        "financial_run_id": financial_run,
        "sha256": {
            "valuation_report": digest(valuation / "report.json"),
            "valuation_source_manifest": market_sha,
            "financial_batch": digest(data / "financial/batch.json"),
            "financial_source_manifest": finance_sha,
            "current_comparison": digest(work / "current.json"),
            "prior_comparison": digest(work / "prior.json"),
            "score_manifest": digest(output_manifest),
        },
    }
    (work / "run-provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--valuation-run", type=int, required=True)
    parser.add_argument("--financial-run", type=int, required=True)
    args = parser.parse_args()
    write(**vars(args), score_run=int(os.environ["GITHUB_RUN_ID"]),
          commit=os.environ["GITHUB_SHA"])
