import unittest

from scripts.compare_sec13f import compare, parse_info_table


def xml(*rows):
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">'
            + ''.join(rows) + '</informationTable>').encode()


def row(cusip="123456789", shares=10, value=50, derivative=False, units="SH"):
    put = "<putCall>CALL</putCall>" if derivative else ""
    return (f"<infoTable><nameOfIssuer>TEST COMPANY</nameOfIssuer><cusip>{cusip}</cusip>"
            f"<value>{value}</value>{put}<shrsOrPrnAmt><sshPrnamt>{shares}</sshPrnamt>"
            f"<sshPrnamtType>{units}</sshPrnamtType></shrsOrPrnAmt></infoTable>")


def meta(period, filed):
    return {"manager_cik": "1067983", "period_end": period, "filed_on": filed,
            "accession": "0001067983-26-000010",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1067983/12345678/infotable.xml"}


class TestSec13FComparison(unittest.TestCase):
    def test_changes_and_disclosure_date(self):
        result = compare(meta("2026-03-31", "2026-05-12"), xml(row(shares=10)),
                         meta("2026-06-30", "2026-08-14"),
                         xml(row(shares=15), row("987654321", 20, 100)),
                         as_of="2026-11-13")
        self.assertEqual(result["first_usable_on"], "2026-08-14")
        self.assertEqual([c["change_type"] for c in result["changes"]], ["increased", "new"])
        self.assertEqual(result["changes"][0]["delta_shares"], "5")
        self.assertIsNone(result["changes"][0]["investment_action"])

    def test_not_available_before_filing(self):
        with self.assertRaisesRegex(ValueError, "future or unpublished"):
            compare(meta("2026-03-31", "2026-05-12"), xml(row()),
                    meta("2026-09-30", "2026-11-16"), xml(row(shares=11)),
                    as_of="2026-11-13")

    def test_exclude_options_and_principal_not_pretend_sale(self):
        positions, counts = parse_info_table(xml(row(), row("987654321", 2, 10, True),
                                                   row("567891234", 3, 12, False, "PRN")))
        self.assertEqual(len(positions), 1)
        self.assertEqual(counts["excluded_non_plain_shares"], 2)

    def test_consolidate_matching_cusip(self):
        positions, _ = parse_info_table(xml(row(shares=10), row(shares=5)))
        self.assertEqual(positions["123456789"]["shares"], 15)

    def test_conflicting_manager_fails_closed(self):
        changed = meta("2026-06-30", "2026-08-14")
        changed["manager_cik"] = "123"
        with self.assertRaisesRegex(ValueError, "different managers"):
            compare(meta("2026-03-31", "2026-05-12"), xml(row()),
                    changed, xml(row()), as_of="2026-11-13")

    def test_reject_xml_entities_and_unsafe_rows(self):
        with self.assertRaisesRegex(ValueError, "entity"):
            parse_info_table(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><informationTable/>')
        with self.assertRaisesRegex(ValueError, "invalid issuer"):
            parse_info_table(xml(row("BAD")))

    def test_reject_bad_period(self):
        with self.assertRaisesRegex(ValueError, "out of order"):
            compare(meta("2026-09-30", "2026-11-10"), xml(row()),
                    meta("2026-06-30", "2026-08-14"), xml(row()),
                    as_of="2026-11-13")


if __name__ == "__main__":
    unittest.main()
