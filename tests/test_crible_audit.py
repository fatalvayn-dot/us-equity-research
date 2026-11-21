"""Crible report remains outside the audited resolver until original evidence is checked."""
import unittest
from equity_research.crible_audit import FIELDS, compare, read_radar_coverage


def report(symbol, missing=()):
    rows = "".join(f"<tr><td>{label}</td><td>{'Mevcut değil' if field in missing else '1'}</td><td>SEC</td></tr>"
                   for field,label in FIELDS.items())
    return f'<article data-gate="x"><h2>{symbol} <small>CIK</small></h2><table>{rows}</table></article>'


def snapshot(symbol, available=()):
    return {"status":"complete","symbols":[symbol],"records":[{
        "symbol":symbol,"in_snapshot":True,"period":"2025-12-31",
        "field_status":{"financial":{f:("available" if f in available else "missing") for f in FIELDS}}
    }]}


class CribleAuditTests(unittest.TestCase):
    def test_only_missing_fields_are_queued(self):
        radar=read_radar_coverage(report("AAPL", {"revenue","capital_expenditure"}))
        result=compare(radar,snapshot("AAPL",{"revenue","capital_expenditure","net_income"}))
        self.assertEqual(result["candidate_count"],2)
        self.assertEqual(result["accepted_facts"],0)
        self.assertEqual(result["fields"]["net_income"]["candidate"],0)
    def test_missing_stays_missing(self):
        r=compare(read_radar_coverage(report("AAPL",{"revenue"})),snapshot("AAPL"))
        self.assertEqual(r["fields"]["revenue"]["union"],0)
    def test_symbol_universe_must_match(self):
        with self.assertRaises(ValueError):
            compare(read_radar_coverage(report("AAPL")),snapshot("MSFT"))
    def test_unknown_vendor_state_fails_closed(self):
        s=snapshot("AAPL")
        s["records"][0]["field_status"]["financial"]["revenue"]="unknown"
        with self.assertRaises(ValueError):
            compare(read_radar_coverage(report("AAPL")),s)
    def test_duplicate_radar_symbol_rejected(self):
        with self.assertRaises(ValueError):
            read_radar_coverage(report("AAPL")+report("AAPL"))
    def test_missing_radar_column_rejected(self):
        with self.assertRaises(ValueError):
            read_radar_coverage('<article><h2>AAPL <small>CIK</small></h2></article>')


if __name__=="__main__":
    unittest.main()
