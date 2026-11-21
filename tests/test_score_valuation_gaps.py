"""Score-to-market-source gap tracing; fixtures do not represent live stocks."""
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.audit_score_valuation_gaps import audit_files, diagnose


def fixtures():
    ids=[dict(symbol=f"T{i}",issuer_id=f"{i+1:010d}") for i in range(100)]
    score=dict(as_of="2026-11-09T12:00:00+00:00",
               companies=[dict(**row,blockers=[("valuation_source_evidence_required"
                        if i in (0,1) else "specialized_or_unmodeled_sector")])
                        for i,row in enumerate(ids)],
               summary=dict(candidates=100,scored_companies=0))
    source=dict(as_of="2026-11-09T11:00:00+00:00",
                report_kind="valuation_source_collection_scope_pending",
                companies=[dict(**row,identity_status="exact_match",
                    share_check=dict(status="verified_dated_share_class"),
                    price_check=dict(status="valid"),
                    history_check=dict(status="valid"),attempts=[]) for row in ids],
                summary=dict(candidates=100))
    source["companies"][0]["share_check"]=dict(status="pending_source_collection")
    source["companies"][0]["history_check"]=dict(status="not_started",deferred_reason="share_class_unverified")
    source["companies"][0]["attempts"]=[dict(stage="companyfacts",status="not_started",
        http_requested=False,deferred_reason="request_budget")]
    source["companies"][1]["price_check"]=dict(status="invalid_data")
    source["companies"][1]["attempts"]=[dict(stage="price",status="invalid_data",
        http_requested=True)]
    return score,source


class SourceGapTraceTests(unittest.TestCase):
    def test_exact_run_and_file_chain_is_required(self):
        score, source = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            score_report = directory / "report.json.gz"
            score_report.write_bytes(gzip.compress(json.dumps(score).encode()))
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({"files": {
                "report.json.gz": hashlib.sha256(score_report.read_bytes()).hexdigest(),
            }}))
            valuation_report = directory / "report.json"
            valuation_report.write_text(json.dumps(source))
            provenance = directory / "run-provenance.json"
            provenance.write_text(json.dumps({
                "schema_version": 1, "score_run_id": 123, "valuation_run_id": 122,
                "sha256": {
                    "score_manifest": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                    "valuation_report": hashlib.sha256(valuation_report.read_bytes()).hexdigest(),
                },
            }))
            inputs = dict(score_report=score_report, valuation_report=valuation_report,
                          provenance=provenance, score_run=123, valuation_run=122)
            result = audit_files(**inputs)
            self.assertEqual(result["score_run_id"], 123)
            self.assertEqual(result["valuation_run_id"], 122)
            self.assertEqual(result["valuation_source_blockers"], 2)

            for key in ("score_run", "valuation_run"):
                with self.subTest(run=key), self.assertRaisesRegex(ValueError, "run kimlikleri"):
                    audit_files(**(inputs | {key: 121}))

            for path, error in ((manifest, "Skor manifestinin"),
                                (score_report, "Skor raporunun"),
                                (valuation_report, "Değerleme raporunun")):
                with self.subTest(path=path):
                    original = path.read_bytes()
                    path.write_bytes(original + b" ")
                    with self.assertRaisesRegex(ValueError, error):
                        audit_files(**inputs)
                    path.write_bytes(original)

    def test_real_source_statuses_are_not_approved_or_zero_filled(self):
        score,source=fixtures()
        result=diagnose(score,source)
        self.assertEqual(result["valuation_source_blockers"],2)
        self.assertEqual(result["source_stage_counts"],{
            "history_check:not_started":1,
            "price_check:invalid_data":1,
            "share_check:pending_source_collection":1})
        self.assertEqual([x["new_gets"] for x in result["companies"]],[0,1])
        self.assertTrue(all(x["score"] is None for x in result["companies"]))
        self.assertFalse(result["mvp_accepted"])
        json.dumps(result)

    def test_failed_identity_and_duplicate_rejected(self):
        score,source=fixtures()
        source["companies"][0]["issuer_id"]="0000000999"
        with self.assertRaisesRegex(ValueError,"kimlik"):
            diagnose(score,source)
        score,source=fixtures()
        score["companies"][1]["symbol"]=score["companies"][0]["symbol"]
        score["companies"][1]["issuer_id"]=score["companies"][0]["issuer_id"]
        with self.assertRaisesRegex(ValueError,"tekrarlı"):
            diagnose(score,source)

    def test_typed_source_failure_survives_gap_trace(self):
        score, source = fixtures()
        source["companies"][1]["price_check"]["failure_detail"] = "stale_quote"
        result = diagnose(score, source)
        self.assertEqual(result["companies"][1]["market_source_states"]["price_check"]
                         ["failure_detail"], "stale_quote")
        self.assertNotIn("failure_detail", result["companies"][0]["market_source_states"]["price_check"])

    def test_cutoff_and_full_cohort_enforced(self):
        score,source=fixtures()
        source["as_of"]="2026-11-10T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"kesimi"):
            diagnose(score,source)
        score,source=fixtures()
        source["companies"].pop()
        with self.assertRaisesRegex(ValueError,"100"):
            diagnose(score,source)

    def test_missing_stage_or_invalid_broken_input_rejected(self):
        score,source=fixtures()
        source["companies"][1]["history_check"].pop("status")
        with self.assertRaisesRegex(ValueError,"bacağı"):
            diagnose(score,source)
        score,source=fixtures()
        source["companies"][1]["attempts"]=[dict(status="invalid_data")]
        with self.assertRaisesRegex(ValueError,"denemesi"):
            diagnose(score,source)

    def test_supported_company_without_market_blocker_never_added(self):
        score,source=fixtures()
        score["companies"][0]["blockers"]=[]
        result=diagnose(score,source)
        self.assertEqual(result["valuation_source_blockers"],1)
        self.assertEqual(result["companies"][0]["symbol"],"T1")


if __name__=="__main__":
    unittest.main()
