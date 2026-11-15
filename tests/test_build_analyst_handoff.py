"""Public daily research handoff checks: timestamp, quality and confidentiality."""
import unittest
from datetime import datetime, timezone
from scripts.build_analyst_handoff import build_handoff


def sample(now="2026-11-13T17:00:00+00:00"):
    brief={"schema_version":1,"created_at":now,"portfolio_positions_included":False,
           "markets":{k:[] for k in ("ABD","BIST","AVRUPA")}}
    packet={"schema_version":1,"created_at":now,"personal_portfolio_included":False,
            "markets":{k:[] for k in ("ABD","BIST","AVRUPA")},"work_queue":[]}
    multi={"schema_version":1,"created_at":now,"personal_portfolio_included":False,
           "instruments":[]}
    return brief, packet, multi


class HandoffTests(unittest.TestCase):
    def test_empty_public_packet(self):
        result=build_handoff(*sample())
        self.assertEqual(result["market_quality"]["ABD"]["tracked"],0)
        self.assertFalse(result["portfolio_data_present"])
        self.assertFalse(result["participation_verified"])
        self.assertFalse(result["investment_decision_present"])
        self.assertFalse(result["work_result_included"])

    def test_mixed_dates_rejected(self):
        a,b,c=sample()
        b["created_at"]="2026-11-13T18:00:01+00:00"
        with self.assertRaises(ValueError):
            build_handoff(a,b,c)

    def test_private_data_rejected(self):
        a,b,c=sample()
        c["personal_portfolio_included"]=True
        with self.assertRaises(ValueError):
            build_handoff(a,b,c)

    def test_no_implicit_approval_with_quote(self):
        a,b,c=sample()
        b["markets"]["ABD"]=[{"symbol":"TSM","source_status":"observed",
                              "market_at":"2026-11-13T16:00:00+00:00"}]
        result=build_handoff(a,b,c)
        self.assertEqual(result["market_quality"]["ABD"]["observed"],1)
        self.assertFalse(result["participation_verified"])


if __name__=="__main__":
    unittest.main()
