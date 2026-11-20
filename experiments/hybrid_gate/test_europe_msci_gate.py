import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experiments.hybrid_gate.europe_msci_gate import (
    index_membership, etf_proxy_holdings, classify, official_page_status
)

class EuropeGateTests(unittest.TestCase):
    def csv(self, path, rows):
        with path.open("w", newline="") as out:
            w=csv.DictWriter(out, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

    def test_official_complete_and_exact_index(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/"constituents.csv"
            self.csv(path,[{"isin":"NL0010273215","name":"A","asof":"2026-11-20","index_name":"MSCI Europe IMI Islamic Index"},
                           {"isin":"DE0007164600","name":"B","asof":"2026-11-20","index_name":"MSCI Europe IMI Islamic Index"}])
            items,meta=index_membership(path,reference_date="2026-11-20",expected_count=2)
            self.assertEqual(len(items),2)
            self.assertEqual(classify({"isin":"NL0010273215"},official=items),"resmi_msci_uyesi")
            self.assertEqual(classify({"isin":"FR0000121972"},official=items),"resmi_listede_yok")
            with self.assertRaises(ValueError):
                index_membership(path,reference_date="2026-11-20",expected_count=428)
            with self.assertRaises(ValueError):
                index_membership(path,reference_date="2026-11-20",expected_count=2,index_name="MSCI Europe Islamic Index")

    def test_proxy_is_not_official(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/"fund.csv"
            self.csv(path,[{"isin":"NL0010273215","name":"A","country":"Netherlands"},
                           {"isin":"US0378331005","name":"Apple","country":"United States"}])
            proxy,meta=etf_proxy_holdings(path,fund_isin="IE000AGFZM58",
                       snapshot_date="2026-11-19",provider="HSBC",benchmark="different MSCI European Islamic fund benchmark")
            self.assertEqual(len(proxy),1)
            self.assertEqual(classify({"isin":"NL0010273215"},proxy=proxy),"etf_portfoyunde_var_endeks_teyitsiz")
            self.assertEqual(classify({"isin":"NL0010273215"},official=set(),proxy=proxy),"resmi_listede_yok")
            self.assertEqual(classify({"ticker":"ASML.AS"},proxy=proxy),"belirsiz_kimlik")
            self.assertNotEqual(meta["source_type"],"msci_official_full_roster")

    def test_block_on_challenge(self):
        info=official_page_status(download=b"<html><title>Challenge Validation</title></html>")
        self.assertFalse(info["full_constituents_available"])
        self.assertEqual(info["page_access"],"challenge")

if __name__=="__main__":
    unittest.main()
