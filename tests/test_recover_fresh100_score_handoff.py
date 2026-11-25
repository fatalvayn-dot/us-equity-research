import base64
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.recover_fresh100_score_handoff import recover


def sha(body):
    return hashlib.sha256(body).hexdigest()


class RecoverFresh100HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.evidence = self.root / "evidence"
        self.candidates = self.root / "candidates.json"
        self.pin = self.root / "pin.json"
        rows = [{"issuer_id": str(i).zfill(10), "symbol": f"S{i}"}
                for i in range(1, 101)]
        self.candidates.write_text(json.dumps({"companies": rows}))
        batch = {"companies": [{**row, "fields": []} for row in rows]}
        fact_body = json.dumps({"cik": 1, "entityName": "One", "facts": {}}).encode()
        fact_url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
        financial_rows = [{"url": fact_url, "sha256": sha(fact_body),
                           "retrieved_at": "2026-11-23T13:00:00+00:00",
                           "body_base64": base64.b64encode(fact_body).decode()}]
        valuation_body = json.dumps({"companies": rows}).encode()
        self._export("batch.json", json.dumps(batch).encode())
        self._export("metadata.json", json.dumps({"companies": rows}).encode(), append=True)
        fsha = self._bundle(self.evidence / "financial-sources", financial_rows)
        vsha = self._bundle(self.evidence / "valuation/source-bundle", financial_rows)
        (self.evidence / "valuation/report.json").write_bytes(valuation_body)
        self.pin.write_text(json.dumps({
            "schema_version": 1,
            "purpose": "fresh100_failed_handoff_artifact_recovery",
            "source_run_id": 45187005935,
            "source_artifact_id": 14825474340,
            "source_artifact_digest": "sha256:" + "a" * 64,
            "candidate_sha256": sha(self.candidates.read_bytes()),
            "financial_observations": 1,
            "financial_bundle_sha256": fsha,
            "valuation_observations": 1,
            "valuation_bundle_sha256": vsha,
            "companyfacts_snapshots": 1,
            "invalid_companyfacts_observations": 0,
            "network_requests_allowed": False,
            "investment_approved": False,
        }))

    def tearDown(self):
        self.temp.cleanup()

    def _export(self, logical, body, append=False):
        root = self.evidence / "financial-evidence"
        root.mkdir(parents=True, exist_ok=True)
        stored = logical + ".gz"
        payload = gzip.compress(body, mtime=0)
        (root / stored).write_bytes(payload)
        path = root / "reports-manifest.json"
        manifest = json.loads(path.read_text()) if append else {"files": []}
        manifest["files"].append({"logical_name": logical, "file": stored,
            "encoding": "gzip", "raw_bytes": len(body), "raw_sha256": sha(body),
            "stored_sha256": sha(payload)})
        path.write_text(json.dumps(manifest))

    def _bundle(self, root, rows):
        root.mkdir(parents=True)
        raw = b"".join(json.dumps(row, separators=(",", ":")).encode() + b"\n"
                       for row in rows)
        compressed = gzip.compress(raw, mtime=0)
        name = "sources.jsonl.gz.part0000"
        (root / name).write_bytes(compressed)
        (root / "manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "format": "gzip-jsonl-public-response-observations-v1",
            "observations": len(rows),
            "compressed_sha256": sha(compressed),
            "parts": [{"file": name, "bytes": len(compressed), "sha256": sha(compressed)}],
            "headers_stored": False,
            "credentials_stored": False,
        }))
        return sha(compressed)

    def test_recovers_three_cohort_locked_directories_without_network(self):
        output = self.root / "output"
        receipt = recover(candidates=self.candidates, recovery_manifest=self.pin,
                          evidence_root=self.evidence, output=output,
                          publish_run_id=999)
        self.assertEqual(receipt["companies"], 100)
        self.assertEqual(receipt["network_requests"], 0)
        self.assertTrue(receipt["recovered_without_provider_requests"])
        self.assertTrue((output / "financial/companyfacts/0000000001.json").is_file())
        self.assertTrue((output / "financial-evidence/live-sources/manifest.json").is_file())
        marker = json.loads((output / "valuation/financial-source-run.json").read_text())
        self.assertEqual(marker["run_id"], 999)
        self.assertEqual(marker["source_run_id"], 45187005935)

    def test_tampered_source_part_fails_before_output(self):
        part = self.evidence / "financial-sources/sources.jsonl.gz.part0000"
        part.write_bytes(part.read_bytes() + b"x")
        output = self.root / "output"
        with self.assertRaisesRegex(ValueError, "bütünlüğü"):
            recover(candidates=self.candidates, recovery_manifest=self.pin,
                    evidence_root=self.evidence, output=output, publish_run_id=999)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
