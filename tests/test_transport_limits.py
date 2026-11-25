import unittest

from equity_research.mvp import transport_limits


class TransportLimitsTests(unittest.TestCase):
    def test_only_nasdaq_gets_longer_bounded_window(self):
        self.assertEqual(transport_limits(['api.nasdaq.com','www.nasdaq.com']),dict(timeout=20.0,budget=60.0))
        self.assertEqual(transport_limits(['api.nasdaq.com']),dict(timeout=20.0,budget=60.0))
        for hosts in (['www.sec.gov'],['data.sec.gov'],['finance.yahoo.com'],['finnhub.io'],['api.nasdaq.com','evil.example']):
            self.assertEqual(transport_limits(hosts),{})

    def test_limits_are_accepted_by_transport_and_bounded(self):
        from equity_research.transport import HttpTransport
        t=HttpTransport(user_agent='Official research contact analyst@example.org',allowed_hosts={'api.nasdaq.com'},**transport_limits(['api.nasdaq.com']))
        self.assertEqual((t.timeout,t.budget),(20.0,60.0));self.assertLessEqual(t.budget,60.0)
