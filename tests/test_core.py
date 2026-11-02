import unittest
from datetime import date
from equity_research.core import Observation, first_valid, classify

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.d = date(2026, 9, 30)
        self.obs = Observation('revenue', 100., 'Yahoo', date(2026, 10, 30), self.d, 'USD', 'CIK1')
    def test_first_valid_stops(self):
        calls = []
        def first(f, i): calls.append('Yahoo'); return self.obs
        def second(f, i): calls.append('SEC'); raise AssertionError('should not call')
        value, attempts = first_valid('revenue','CIK1','USD',date(2025,1,1), [('Yahoo',first),('SEC',second)])
        self.assertEqual(value.value, 100.)
        self.assertEqual(calls,['Yahoo'])
        self.assertEqual(attempts[0]['status'],'valid')
    def test_invalid_falls_back(self):
        invalid = Observation('revenue', 100., 'Yahoo', date(2026,10,30),self.d,'EUR','CIK1')
        sec = Observation('revenue', 99., 'SEC',date(2026,10,30),self.d,'USD','CIK1')
        result, attempts = first_valid('revenue','CIK1','USD',date(2025,1,1), [('Yahoo',lambda f,i: invalid),('SEC',lambda f,i:sec)])
        self.assertEqual(result.source,'SEC')
        self.assertEqual([a['status'] for a in attempts],['invalid','valid'])
    def test_error_not_negative_evidence(self):
        result, attempts = first_valid('revenue','CIK1','USD',date(2025,1,1), [('Yahoo',lambda f,i:1/0)])
        self.assertIsNone(result)
        self.assertEqual(attempts[0]['status'],'error')
    def test_unknown_not_approved(self):
        self.assertEqual(classify('common_stock',None,False,True),'pending_evidence')
    def test_verified_exclusion(self):
        self.assertEqual(classify('common_stock',True,None,False),'excluded_verified')
    def test_etf(self):
        self.assertEqual(classify('etf',False,False,True),'out_of_scope')
    def test_eligible(self):
        self.assertEqual(classify('common_stock',False,False,True),'eligible_for_scoring')

if __name__ == '__main__': unittest.main()
