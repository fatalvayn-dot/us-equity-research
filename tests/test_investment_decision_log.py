import json
import tempfile
import unittest
from pathlib import Path
from scripts.investment_decision_log import append_event, verify_log

THESIS = {"event": "thesis", "decision_id": "20261112-MSFT-01",
          "as_of": "2026-11-12T18:00:00+00:00",
          "action": "BEKLE", "market": "ABD", "symbol": "MSFT",
          "rationale": "Alım için yeterli net risk getiri üstünlüğü bulunmadı.",
          "invalidation": "Yeni bilanço beklentileri değiştirirse tekrar değerlendir.",
          "participation_status": "unknown"}
OUTCOME = {"event": "outcome", "decision_id": "20261112-MSFT-01",
           "as_of": "2027-02-12T18:00:00+00:00",
           "result": "inconclusive",
           "evidence_url": "https://www.sec.gov/edgar/search/",
           "analysis": "Mevcut kanıtlar belirli bir tahmin doğruluğu ispatlamıyor."}


class JournalTests(unittest.TestCase):
    def test_immutable_event_chain_and_private_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "decisions.json"
            first = append_event(path, THESIS)
            second = append_event(path, OUTCOME)
            records = json.loads(path.read_text())
            self.assertEqual(verify_log(records), second["sha256"])
            self.assertEqual(first["index"], 0)
            records[0]["rationale"] = "Ardından değiştirilmiş."
            with self.assertRaises(ValueError):
                verify_log(records)

    def test_no_unverified_buy(self):
        with tempfile.TemporaryDirectory() as root:
            bad = dict(THESIS, action="AL")
            with self.assertRaises(ValueError):
                append_event(Path(root) / "log.json", bad)

    def test_no_result_without_prior_thesis_and_no_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "log.json"
            with self.assertRaises(ValueError):
                append_event(path, OUTCOME)
            append_event(path, THESIS)
            with self.assertRaises(ValueError):
                append_event(path, THESIS)


if __name__ == "__main__":
    unittest.main()
