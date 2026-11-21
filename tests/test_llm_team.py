import unittest
from scripts.llm_team import sanitize,orchestrate,ask

class LLMTeamTests(unittest.TestCase):
    def test_no_portfolio_leak(self):
        r={"summary":{"status":"ok","current_forecasts":1},"research":{"forecasts":[{"symbol":"SPY","direction":"yukari","private":"secret"}],"portfolio":"secret"}}
        self.assertNotIn("secret",str(sanitize(r)))
    def test_handoffs(self):
        calls=[]
        def fake(p):
            calls.append(p)
            return {"choices":[{"message":{"content":"step "+str(len(calls))}}]}
        r=orchestrate({"summary":{"status":"ok"},"research":{"forecasts":[]}},transport=fake)
        self.assertEqual(len(calls),5)
        self.assertIn("step 1",calls[1]["messages"][1]["content"])
        self.assertIn("step 4",calls[4]["messages"][1]["content"])
        self.assertEqual(r["agents"]["manager_report"],"step 5")
    def test_unknown_role(self):
        with self.assertRaises(ValueError): ask("broker",{},transport=lambda _: {})
    def test_no_key(self):
        import os
        key=os.environ.pop("OPENAI_API_KEY",None)
        try:
            with self.assertRaises(RuntimeError): ask("manager",{})
        finally:
            if key is not None: os.environ["OPENAI_API_KEY"]=key
