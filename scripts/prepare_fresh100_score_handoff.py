"""Prepare minimal, cohort-locked score artifacts from one fresh100 run."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

if __package__:
    from .verify_score_input_cohort import verify
else:
    from verify_score_input_cohort import verify


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(*, candidates: Path, financial: Path, financial_sources: Path,
            valuation: Path, output: Path, run_id: int) -> dict:
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("run ID pozitif olmalıdır")
    candidate_rows = json.loads(candidates.read_text())
    batch = json.loads((financial / "batch.json").read_text())
    valuation_report = json.loads((valuation / "report.json").read_text())
    if len(candidate_rows) != 100:
        raise ValueError("fresh100 devri tam 100 aday gerektirir")
    expected = {(row["issuer_id"], row["symbol"]) for row in candidate_rows}
    if len(expected) != 100:
        raise ValueError("aday kimlikleri yineleniyor")
    result = verify(batch, valuation_report)
    actual = {(row["issuer_id"], row["symbol"]) for row in batch["companies"]}
    if actual != expected:
        raise ValueError("fresh100 aday dosyası ile finansal kohort uyuşmuyor")

    required = [financial / "metadata.json", financial / "companyfacts",
                financial_sources / "manifest.json",
                valuation / "source-bundle/manifest.json"]
    if any(not path.exists() for path in required):
        raise ValueError("skor devri için zorunlu kaynak dosyası eksik")

    if output.exists():
        raise ValueError("skor devri hedefi boş olmalıdır")
    finance_out = output / "financial"
    evidence_out = output / "financial-evidence"
    valuation_out = output / "valuation"
    finance_out.mkdir(parents=True)
    evidence_out.mkdir(parents=True)
    valuation_out.mkdir(parents=True)
    for name in ("batch.json", "metadata.json"):
        shutil.copy2(financial / name, finance_out / name)
    shutil.copytree(financial / "companyfacts", finance_out / "companyfacts")
    shutil.copytree(financial_sources, evidence_out / "live-sources")
    shutil.copy2(valuation / "report.json", valuation_out / "report.json")
    shutil.copytree(valuation / "source-bundle", valuation_out / "source-bundle")
    (valuation_out / "financial-source-run.json").write_text(
        json.dumps({"run_id": run_id}) + "\n")

    receipt = {
        "schema_version": 1,
        "purpose": "fresh100_same_run_score_handoff",
        "source_run_id": run_id,
        "companies": result["companies"],
        "cohort_match": result["cohort_match"],
        "candidate_sha256": digest(candidates),
        "financial_batch_sha256": digest(financial / "batch.json"),
        "financial_source_manifest_sha256": digest(financial_sources / "manifest.json"),
        "valuation_report_sha256": digest(valuation / "report.json"),
        "valuation_source_manifest_sha256": digest(valuation / "source-bundle/manifest.json"),
        "scores_generated": 0,
        "investment_approved": False,
    }
    (valuation_out / "cohort-handoff.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidates", "financial", "financial-sources",
                 "valuation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    print(json.dumps(prepare(**vars(parser.parse_args())), ensure_ascii=False))


if __name__ == "__main__":
    main()
