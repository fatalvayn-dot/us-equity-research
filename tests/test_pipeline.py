import unittest
from datetime import date,datetime,timezone
from decimal import Decimal

from equity_research.models import Fact,FactQuery,Source
from equity_research.pipeline import DeferredProvider,research_resolver
from equity_research.providers import Resolver,Status

NOW=datetime(2026,11,1,22,30,tzinfo=timezone.utc)
QUERY=FactQuery('0000320193','assets',None,date(2025,9,27),'USD','currency','us-gaap:Assets')


class Provider:
    def __init__(self,source,value):self.source,self.value=source,value
    def fetch(self,request):
        if self.value is None:return None
        return Fact(request.issuer_id,'assets',Decimal(self.value),self.source,None,request.period_end,'USD','currency',NOW,NOW,'us-gaap:Assets','https://example.org/synthetic')


class PipelineTests(unittest.TestCase):
    def test_later_factory_including_invalid_credentials_is_untouched(self):
        called=[]
        def first():called.append('Yahoo');return Provider(Source.YAHOO,123)
        def later():called.append('Finnhub');raise ValueError('synthetic-secret')
        resolver=Resolver([DeferredProvider(Source.FINNHUB,later),DeferredProvider(Source.YAHOO,first)],clock=lambda:NOW)
        self.assertEqual(called,[])
        result=resolver.resolve_current(QUERY)
        self.assertEqual(result.fact.source,Source.YAHOO)
        self.assertEqual(called,['Yahoo'])

    def test_only_reached_configuration_error_is_reported_safely(self):
        def broken():raise ValueError('synthetic-secret')
        result=Resolver([DeferredProvider(Source.NASDAQ,broken)],clock=lambda:NOW).resolve_current(QUERY)
        self.assertEqual(result.attempts[2].status,Status.INVALID_CONFIGURATION)
        self.assertNotIn('synthetic-secret',repr(result))

    def test_factory_is_reused_between_prepare_and_fetch(self):
        called=[]
        def factory():called.append(True);return Provider(Source.SEC,123)
        provider=DeferredProvider(Source.SEC,factory)
        result=Resolver([provider],clock=lambda:NOW).resolve_current(QUERY)
        self.assertEqual(len(called),1)
        self.assertEqual(result.fact.value,Decimal(123))

    def test_wrong_factory_source_never_relabels_observation(self):
        provider=DeferredProvider(Source.SEC,lambda:Provider(Source.YAHOO,123))
        result=Resolver([provider],clock=lambda:NOW).resolve_current(QUERY)
        self.assertIsNone(result.fact)
        self.assertEqual(result.attempts[1].status,Status.INVALID_CONFIGURATION)

    def test_pipeline_construction_needs_no_secret_or_connection(self):
        # Lazy factory setup intentionally does not inspect the invalid placeholder
        # identity or create a transport until that source is needed.
        resolver=research_resolver(directory=None,symbol='AAPL',user_agent='Synthetic tests',clock=lambda:NOW)
        self.assertEqual(list(resolver.providers),list(Source))
        self.assertTrue(all(p.instance is None for p in resolver.providers.values()))
