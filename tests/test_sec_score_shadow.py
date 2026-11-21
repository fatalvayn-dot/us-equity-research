"""Two-source immutable SEC SHA corroboration in a local score integration.

All numeric fixture values are invented *test copies* of two public claims.
Successful synthetic checks do NOT certify a live SEC fetch or an investment.
"""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from equity_research.sec_attestation import guard_selected_batch
from scripts.live_stage1_sec_verification import PUBLIC_CLAIMS, companyconcept_url, run_once
from scripts.build_current_scores import build

CUT = datetime(2026, 11, 19, 16, 0, tzinfo=timezone.utc)


def prepare(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    raw = {}
    for c in PUBLIC_CLAIMS:
        body = json.dumps({
            "cik": int(c["cik"]), "taxonomy": c["taxonomy"], "tag": c["concept"],
            "units": {"USD": [{"accn": c["accession"], "form": "10-K",
                              "end": c["end"], "filed": c["filed"],
                              "val": c["value"]}]},
        }, sort_keys=True).encode()
        raw[companyconcept_url(c)] = body
        (directory / f"{c['cik']}_us-gaap_Liabilities.json").write_bytes(body)
    manifest = run_once(raw, fetched_at="2026-11-19T15:00:00+00:00")
    path = directory.parent / "stage1.json"
    path.write_text(json.dumps(manifest))
    return manifest, path


def batch():
    return {
        "schema_version": 1,
        "generated_at": "2026-11-19T15:15:00+00:00",
        "companies": [
            {"issuer_id": c["cik"], "symbol": "NVDA" if i == 0 else "SWKS",
             "fields": [{"query": {"field": "liabilities"}, "state": "collected",
                         "fact": {
                             "issuer_id": c["cik"], "field": "liabilities",
                             "value": str(c["value"]), "period_start": None,
                             "period_end": c["end"], "currency": "USD",
                             "accounting_definition": "us-gaap:Liabilities",
                             "filing_accession": c["accession"],
                         }}]} for i, c in enumerate(PUBLIC_CLAIMS)
        ],
    }


class SecScoreShadowTests(unittest.TestCase):
    def test_real_source_bytes_contract_replayed_into_two_selected_facts(self):
        with tempfile.TemporaryDirectory() as root:
            raw_dir = Path(root) / "raw"
            manifest, _ = prepare(raw_dir)
            original = batch()
            copy = deepcopy(original)
            report = guard_selected_batch(original, raw_dir, manifest, as_of=CUT)
            self.assertEqual(report["selected_financial_fact_matches"], 2)
            self.assertEqual(report["verified_sec_original_sources"], 2)
            self.assertEqual(report["issuer_period_not_selected"], [])
            self.assertEqual(report["financial_facts_substituted"], 0)
            self.assertFalse(report["provider_order_changed"])
            self.assertFalse(report["investment_approved"])
            self.assertEqual(original, copy)

    def test_wrong_selected_fact_aborts_instead_of_writing_zero_or_score(self):
        with tempfile.TemporaryDirectory() as root:
            raw_dir = Path(root) / "raw"; manifest, _ = prepare(raw_dir)
            for field, changed in (("value", "0"),
                                   ("accounting_definition", "us-gaap:Assets"),
                                   ("currency", "EUR")):
                b = batch()
                b["companies"][1]["fields"][0]["fact"][field] = changed
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "conflicts"):
                    guard_selected_batch(b, raw_dir, manifest, as_of=CUT)

    def test_different_period_is_unmatched_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            raw_dir = Path(root) / "raw"; manifest, _ = prepare(raw_dir)
            b = batch()
            b["companies"][0]["fields"][0]["fact"]["period_end"] = "2025-01-26"
            result = guard_selected_batch(b, raw_dir, manifest, as_of=CUT)
            self.assertEqual(result["selected_financial_fact_matches"], 1)
            self.assertEqual(result["issuer_period_not_selected"], ["0001045810"])

    def test_changed_original_sec_bytes_and_false_manifest_abort(self):
        with tempfile.TemporaryDirectory() as root:
            raw_dir = Path(root) / "raw"; manifest, _ = prepare(raw_dir)
            p = raw_dir / "0001045810_us-gaap_Liabilities.json"
            p.write_bytes(p.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                guard_selected_batch(batch(), raw_dir, manifest, as_of=CUT)
            _, path = prepare(raw_dir)
            m = json.loads(path.read_text()); m["records"][0]["reported_value"] = "0"
            with self.assertRaisesRegex(ValueError, "conflict"):
                guard_selected_batch(batch(), raw_dir, m, as_of=CUT)
            m = json.loads(path.read_text()); m["replay_identical"] = False
            with self.assertRaises(ValueError):
                guard_selected_batch(batch(), raw_dir, m, as_of=CUT)

    def test_score_builder_optional_shadow_does_not_change_selected_points(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            raw_dir = base / "raw"
            manifest, proof = prepare(raw_dir)
            financial = base / "financial.json"
            financial.write_text(json.dumps(batch()))
            current = base / "current.json"; prior = base / "prior.json"
            for f in (current, prior):
                f.write_text(json.dumps({"companies": []}))
            sources = base / "sources"; sources.mkdir()
            (sources / "manifest.json").write_text("{}")
            synthetic = {"schema_version": 1, "as_of": CUT.isoformat(),
                         "model_version": "synthetic", "summary": {
                             "candidates": 2, "scored_companies": 0, "unscored": 2},
                         "companies": [{"issuer_id": c["cik"], "symbol": s,
                                        "total_score": None} for c, s in zip(PUBLIC_CLAIMS, ("NVDA","SWKS"))],
                         "ranking": [], "input_provenance": {"batches": {}}}
            with (patch("scripts.build_current_scores.read_bundle", return_value=iter(())),
                  patch("scripts.build_current_scores.build_score_report", side_effect=lambda *a, **k: deepcopy(synthetic)),
                  patch("scripts.build_current_scores.render_score_markdown", return_value="test\n"),
                  patch("scripts.build_current_scores.render_score_html", return_value="<html/>")):
                no_sh = build(financial=financial, current=current, prior=prior,
                              sources=sources, output=base / "base", as_of=CUT)
                with_sh = build(financial=financial, current=current, prior=prior,
                                sources=sources, output=base / "with", as_of=CUT,
                                sec_stage1=proof, sec_raw_dir=raw_dir)
            self.assertEqual(no_sh["summary"], with_sh["summary"])
            self.assertEqual(no_sh["companies"], with_sh["companies"])
            self.assertEqual(no_sh["ranking"], with_sh["ranking"])
            self.assertNotIn("supplemental_sec_evidence", no_sh)
            self.assertEqual(with_sh["supplemental_sec_evidence"]["selected_financial_fact_matches"], 2)
            data = json.loads(gzip.decompress((base / "with" / "report.json.gz").read_bytes()))
            self.assertFalse(data["supplemental_sec_evidence"]["investment_approved"])

    def test_score_builder_fail_closed_before_creating_output(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root);raw_dir=base/"raw";manifest,proof=prepare(raw_dir)
            financial=base/"f.json";financial.write_text(json.dumps(batch()))
            b=json.loads(financial.read_text())
            b["companies"][0]["fields"][0]["fact"]["value"] = "999"
            financial.write_text(json.dumps(b))
            current=base/"c.json";prior=base/"p.json"
            current.write_text("{}");prior.write_text("{}")
            sources=base/"sources";sources.mkdir()
            with self.assertRaisesRegex(ValueError, "conflicts"):
                build(financial=financial,current=current,prior=prior,sources=sources,
                      output=base/"output",as_of=CUT,sec_stage1=proof,sec_raw_dir=raw_dir)
            self.assertFalse((base/"output").exists())


if __name__=="__main__":
    unittest.main()
