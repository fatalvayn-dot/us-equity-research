"""Lazy current-source wiring. Later providers are untouched after success."""
from .companyfacts import SecCompanyFacts
from .finnhub import FinnhubConfig,FinnhubReported
from .models import Source
from .nasdaq_financials import NasdaqFinancials
from .providers import ProviderFailure,Resolver,Status
from .transport import HttpTransport
from .yahoo import YahooAssets


class DeferredProvider:
    def __init__(self,source,factory):
        self.source,self.factory=source,factory
        self.instance=None

    def _get(self):
        if self.instance is None:
            try:
                instance=self.factory()
                if instance.source is not self.source:raise ValueError("factory source mismatch")
            except (ValueError,TypeError):raise ProviderFailure(Status.INVALID_CONFIGURATION) from None
            self.instance=instance
        return self.instance

    def prepare(self,query):
        provider=self._get()
        prepare=getattr(provider,"prepare",None)
        if prepare is not None:prepare(query)

    def fetch(self,request):return self._get().fetch(request)


def research_resolver(*,directory,symbol,user_agent,cache_dir="data/cache/companyfacts",clock=None,response_archive=None,transport_factory=None):
    def http(hosts):
        if transport_factory is not None:return transport_factory(hosts)
        if response_archive is not None:
            from .response_archive import ArchivedTransport
            return ArchivedTransport(archive=response_archive,user_agent=user_agent,allowed_hosts=set(hosts))
        return HttpTransport(user_agent=user_agent,allowed_hosts=set(hosts))
    def sec():
        transport=http(["data.sec.gov"])
        if response_archive is not None:
            from .response_archive import ArchivedCompanyFacts
            return ArchivedCompanyFacts(transport,archive=response_archive,cache_dir=cache_dir,clock=clock)
        return SecCompanyFacts(transport,cache_dir=cache_dir,clock=clock)
    factories={
        Source.YAHOO:lambda:YahooAssets(http(["query1.finance.yahoo.com"]),directory=directory,symbol=symbol,clock=clock),
        Source.SEC:sec,
        Source.NASDAQ:lambda:NasdaqFinancials(http(["api.nasdaq.com","www.nasdaq.com"]),directory=directory,symbol=symbol,clock=clock),
        Source.FINNHUB:lambda:FinnhubReported(FinnhubConfig.from_environment(),user_agent=user_agent,clock=clock),
    }
    return Resolver([DeferredProvider(source,factory) for source,factory in factories.items()],clock=clock)
