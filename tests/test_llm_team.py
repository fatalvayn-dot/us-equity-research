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
    def test_news_summary_is_numeric_only(self):
        report = {"summary": {"status": "ok"},
                  "research": {"forecasts": [], "news": {
                      "status": "ok", "risk_count": 1,
                      "items": [{"title": "SECRET_NEWS_HEADLINE",
                                 "url": "https://secret.example"}]}}}
        clean = sanitize(report)
        self.assertEqual(clean["public_news_observation"]["headline_count"], 1)
        self.assertEqual(clean["public_news_observation"]["risk_keyword_count"], 1)
        self.assertNotIn("SECRET_NEWS_HEADLINE", str(clean))
        self.assertNotIn("https://secret.example", str(clean))

    def test_http_error_status_without_provider_body_or_secret(self):
        import os
        import urllib.error
        from unittest.mock import patch
        response = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions", 401,
            "private credential header", {}, None)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret_value"}):
            with patch("scripts.llm_team.urllib.request.urlopen", side_effect=response):
                with self.assertRaisesRegex(RuntimeError, "HTTP status: 401") as ctx:
                    ask("manager", {})
        self.assertNotIn("secret_value", str(ctx.exception))
        self.assertNotIn("private credential header", str(ctx.exception))

    def test_reasoning_length_retry_keeps_free_model(self):
        seen = []
        def fake(payload):
            seen.append(payload)
            if len(seen) == 1:
                return {"choices": [{"finish_reason": "length",
                                     "message": {"content": ""}}],
                        "usage": {"completion_tokens": 900}}
            return {"choices": [{"finish_reason": "stop",
                                 "message": {"content": "Kanıt yetersiz; işlem yok."}}]}
        answer = ask("manager", {"summary": "AAPL"}, transport=fake)
        self.assertIn("Kanıt yetersiz", answer)
        self.assertEqual([p["model"] for p in seen],
                         ["openrouter/free", "openrouter/free"])
        self.assertEqual([p["max_tokens"] for p in seen], [900, 2400])

    def test_empty_stop_is_failure_without_retry_or_leak(self):
        requests = []
        def fake(payload):
            requests.append(payload)
            return {"choices": [{"finish_reason": "stop",
                                 "message": {"content": "", "reasoning": "PRIVATE_PROVIDER_REASONING"}}],
                    "usage": {"completion_tokens": 87}}
        with self.assertRaisesRegex(RuntimeError, "finish=stop") as ctx:
            ask("manager", {}, transport=fake)
        self.assertEqual(len(requests), 1)
        self.assertNotIn("PRIVATE_PROVIDER_REASONING", str(ctx.exception))

    def test_length_retry_still_empty_remains_failure(self):
        requests = []
        def fake(payload):
            requests.append(payload)
            return {"choices": [{"finish_reason": "length", "message": {"content": None}}],
                    "usage": {"completion_tokens": payload["max_tokens"]}}
        with self.assertRaisesRegex(RuntimeError, "finish=length"):
            ask("manager", {}, transport=fake)
        self.assertEqual(len(requests), 2)

    def test_unknown_role(self):
        with self.assertRaises(ValueError): ask("broker",{},transport=lambda _: {})
    def test_no_key(self):
        import os
        key=os.environ.pop("OPENROUTER_API_KEY",None)
        try:
            with self.assertRaises(RuntimeError): ask("manager",{})
        finally:
            if key is not None: os.environ["OPENROUTER_API_KEY"]=key

    def test_free_router_is_locked(self):
        import os
        old=os.environ.get("RADAR_LLM_MODEL")
        os.environ["RADAR_LLM_MODEL"]="openai/gpt-4.1"
        seen=[]
        def mock(request):
            seen.append(request)
            return {"choices":[{"message":{"content":"test"}}]}
        try:
            ask("manager",{},transport=mock)
            self.assertEqual(seen[0]["model"],"openrouter/free")
        finally:
            if old is None: os.environ.pop("RADAR_LLM_MODEL",None)
            else: os.environ["RADAR_LLM_MODEL"]=old
