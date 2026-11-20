import unittest
from experiments.hybrid_gate.xktum_only import parse_official_csv, compare

def sample(rows):
    lines=[
      "BILESEN KODU;BULTEN_ADI;ENDEKS KODU;ENDEKS ADI;ENDEKS INGILIZCE ADI;TARIH(GG/AA/YYYY)",
      "CONSTITUENT CODE;CONSTITUENT NAME;INDEX CODE;INDEX NAME IN TURKISH;INDEX NAME IN ENGLISH;DATE(DD/MM/YYYY)",
    ]+rows
    return ("\n".join(lines)+"\n").encode("utf-8")

class XktumTest(unittest.TestCase):
    def test_only_exact_xktum_not_xk100(self):
        m,info=parse_official_csv(sample([
            "ASELS.E;ASELSAN;XKTUM;BIST KATILIM TUM;PARTICIPATION ALL;20/11/2026",
            "BIMAS.E;BIM;XK100;BIST KATILIM 100;PARTICIPATION 100;20/11/2026",
            "ALBRK.E;ALBARAKA;XKTUM;BIST KATILIM TUM;PARTICIPATION ALL;20/11/2026"]))
        self.assertEqual(sorted(m),["ALBRK.IS","ASELS.IS"])
        self.assertEqual(info["dates"],["2026-11-20"])
    def test_no_secondary_bank_exclusion(self):
        m,_=parse_official_csv(sample(["ALBRK.E;ALBARAKA;XKTUM;BIST;BIST;20/11/2026"]))
        self.assertIn("ALBRK.IS",m)
    def test_nonmember_is_not_noncompliant(self):
        m,_=parse_official_csv(sample(["ASELS.E;ASELSAN;XKTUM;BIST;BIST;20/11/2026"]))
        rows,missing=compare([{"symbol":"ASELS.IS","company_name":"A","source":["yfinance"]},
                              {"symbol":"TEST.IS","company_name":"B","source":["yfinance"]}],m)
        self.assertEqual(rows[1]["status"],"xktum_uyesi_degil")
        self.assertFalse(rows[1]["financial_screen_run"])
    def test_reject_duplicate(self):
        v="ASELS.E;ASELSAN;XKTUM;BIST;BIST;20/11/2026"
        with self.assertRaises(ValueError):
            parse_official_csv(sample([v,v]))
    def test_reject_wrong_index_or_missing(self):
        with self.assertRaises(ValueError):
            parse_official_csv(sample(["ASELS.E;ASELSAN;XK100;BIST;BIST;20/11/2026"]))
if __name__=="__main__":unittest.main()
