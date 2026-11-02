import argparse
import json
import os
from dataclasses import asdict
from datetime import date

from . import __version__
from .policy import SCORE_WEIGHTS
from .providers import ProviderFailure,Status
from .sec import SecDirectory
from .transport import HttpTransport
from .cache import encode
from .companyfacts import SecCompanyFacts, TAGS
from .models import FactQuery
from .providers import Resolver
from .nasdaq_screener import NasdaqScreener
from .finnhub import FinnhubConfig,FinnhubReported
from .pipeline import research_resolver


def main():
    parser = argparse.ArgumentParser(description="US Equity Research foundation")
    parser.add_argument("command", choices=["status", "sec-directory", "sec-fact", "nasdaq-discovery", "finnhub-fact", "research-fact", "research-batch", "research-report", "mvp-run"])
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT"))
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--cik")
    parser.add_argument("--field", choices=list(TAGS))
    parser.add_argument("--period-start")
    parser.add_argument("--period-end")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--cache-dir", default="data/cache/companyfacts")
    parser.add_argument("--frequency",choices=["annual","quarterly"],default="annual")
    parser.add_argument("--plan")
    parser.add_argument("--checkpoint",default="data/batch.sqlite")
    parser.add_argument("--output")
    parser.add_argument("--max-new-fields",type=int)
    parser.add_argument("--input")
    parser.add_argument("--markdown")
    parser.add_argument("--candidates")
    parser.add_argument("--state-dir",default="data/mvp")
    parser.add_argument("--max-new-documents",type=int,default=100)
    args = parser.parse_args()
    if args.command == "mvp-run":
        from pathlib import Path
        from .mvp import run_mvp
        from .batch import RunBusy
        if not args.candidates or not args.user_agent:
            parser.error("mvp-run requires --candidates and identifying --user-agent")
        try:
            def progress(row):print(json.dumps(row),flush=True)
            run_mvp(json.loads(Path(args.candidates).read_text()),state_dir=args.state_dir,
                user_agent=args.user_agent,max_new_documents=args.max_new_documents,
                max_new_fields=args.max_new_fields,progress=progress)
        except (ValueError,KeyError,TypeError,OSError,RunBusy,ProviderFailure) as exc:
            print(json.dumps(dict(status="mvp_run_error",error_type=type(exc).__name__,mvp_accepted=False)))
            raise SystemExit(2) from None
        return
    if args.command == "research-report":
        from pathlib import Path
        import tempfile
        from .reporting import build_report, render_markdown
        if not args.input or not args.output:
            parser.error("research-report requires --input batch.json and --output report.json")
        if len({str(Path(p).resolve()) for p in (args.input,args.output,args.markdown) if p}) != (3 if args.markdown else 2):
            parser.error("input and report destinations must be distinct")
        def save(path, content):
            target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=target.parent,delete=False) as handle:
                    temporary=handle.name;handle.write(content);handle.flush();os.fsync(handle.fileno())
                os.replace(temporary,target)
            finally:
                if temporary and os.path.exists(temporary):os.unlink(temporary)
        try:
            report=build_report(json.loads(Path(args.input).read_text()))
            save(args.output,json.dumps(report,default=encode,indent=2)+"\n")
            if args.markdown:save(args.markdown,render_markdown(report))
            print(json.dumps(report['summary']))
        except (ValueError,KeyError,TypeError,OSError) as exc:
            print(json.dumps(dict(status="report_error",error_type=type(exc).__name__,mvp_accepted=False)))
            raise SystemExit(2) from None
        return
    if args.command == "research-batch":
        from pathlib import Path
        import tempfile
        from .batch import BatchRunner,BatchStore,load_plan,RunBusy
        if not args.user_agent or not args.plan or not args.output:
            parser.error("research-batch requires --user-agent, --plan and --output")
        try:
            companies=load_plan(json.loads(Path(args.plan).read_text()))
            directory=None
            def factory(company):
                nonlocal directory
                if directory is None:
                    directory=SecDirectory(HttpTransport(user_agent=args.user_agent,allowed_hosts={"www.sec.gov"})).fetch()
                if directory.lookup(company.symbol,expected_cik=company.issuer_id) is None:
                    raise ProviderFailure(Status.SYMBOL_MISMATCH)
                return research_resolver(directory=directory,symbol=company.symbol,
                                         user_agent=args.user_agent,cache_dir=args.cache_dir)
            Path(args.checkpoint).parent.mkdir(parents=True,exist_ok=True)
            store=BatchStore(args.checkpoint)
            try:report=BatchRunner(store,factory).run(companies,max_new_fields=args.max_new_fields)
            finally:store.close()
            destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode="w",dir=destination.parent,delete=False) as handle:
                    temporary=handle.name
                    json.dump(report,handle,default=encode,indent=2)
                    handle.flush();os.fsync(handle.fileno())
                os.replace(temporary,destination)
            finally:
                if temporary and os.path.exists(temporary):os.unlink(temporary)
            print(json.dumps(report["summary"]))
            if any(c["readiness"]=="pending_fields_and_scope" for c in report["companies"]):raise SystemExit(2)
        except (ValueError,KeyError,TypeError,OSError,RunBusy) as exc:
            print(json.dumps({"status":"batch_error","error_type":type(exc).__name__,"financial_acceptance":False}))
            raise SystemExit(2) from None
        return
    if args.command == "nasdaq-discovery":
        if not args.user_agent:
            parser.error("explicit identifying User-Agent is required")
        try:
            transport=HttpTransport(user_agent=args.user_agent,allowed_hosts={"api.nasdaq.com"})
            snapshot=NasdaqScreener(transport,page_size=10000).fetch()
        except (ProviderFailure,ValueError) as exc:
            print(json.dumps({"status":exc.status.value if isinstance(exc,ProviderFailure) else "invalid_configuration",
                              "reason":exc.reason.value if isinstance(exc,ProviderFailure) and exc.reason else None,
                              "http_status":exc.http_status if isinstance(exc,ProviderFailure) else None,
                              "active_common_universe_accepted":False}))
            raise SystemExit(2) from None
        print(json.dumps({"records":len(snapshot.records),"pages":len(snapshot.pages),
                          "source_asof_label":snapshot.source_asof_label,
                          "source_urls":[page.response.url for page in snapshot.pages],
                          "active_common_universe_accepted":False,"financial_acceptance":False,
                          "missing_scope_evidence":["exchange","ETF flag","test flag","active status","verified security type"]},indent=2))
        return
    if args.command in ("sec-fact","finnhub-fact","research-fact"):
        if not all((args.cik,args.field,args.period_end)) or (args.command in ("sec-fact","research-fact") and not args.user_agent):
            parser.error("financial diagnostics require --cik, --field, --period-end; SEC also requires identifying User-Agent")
        try:
            tag, instant = TAGS[args.field]
            if not instant and not args.period_start:
                parser.error("duration fields require --period-start")
            if instant and args.period_start:
                parser.error("instant fields must not have --period-start")
            if args.command=="research-fact":
                if len(args.symbol)!=1:parser.error("research-fact requires exactly one --symbol")
                identity=SecDirectory(HttpTransport(user_agent=args.user_agent,allowed_hosts={"www.sec.gov"})).fetch()
                if identity.lookup(args.symbol[0],expected_cik=args.cik) is None:
                    raise ProviderFailure(Status.SYMBOL_MISMATCH)
                resolver=research_resolver(directory=identity,symbol=args.symbol[0],user_agent=args.user_agent,cache_dir=args.cache_dir)
            elif args.command=="finnhub-fact":
                config=FinnhubConfig.from_environment()
                if not config.configured:
                    print(json.dumps({"status":"not_configured","source":"Finnhub","network_attempted":False,"financial_acceptance":False}))
                    raise SystemExit(2)
                provider=FinnhubReported(config,user_agent=args.user_agent or "US Equity Research",frequency=args.frequency)
            else:
                transport = HttpTransport(user_agent=args.user_agent, allowed_hosts={"data.sec.gov"})
                provider = SecCompanyFacts(transport, cache_dir=args.cache_dir)
            query = FactQuery(args.cik, args.field, date.fromisoformat(args.period_start) if args.period_start else None,
                              date.fromisoformat(args.period_end), args.currency, "currency", "us-gaap:"+tag)
            resolution = (resolver if args.command=="research-fact" else Resolver([provider])).resolve_current(query)
            print(json.dumps({"fact": asdict(resolution.fact) if resolution.fact else None,
                              "attempts": [asdict(a) for a in resolution.attempts],
                              "as_of": resolution.as_of,
                              "financial_acceptance": False,
                              "mode": "ordered current sources" if args.command=="research-fact" else "single-source diagnostic; other sources may be unconfigured"}, default=encode, indent=2))
            if resolution.fact is None:
                raise SystemExit(2)
        except (ProviderFailure, ValueError) as exc:
            status = exc.status.value if isinstance(exc, ProviderFailure) else "invalid_configuration"
            print(json.dumps({"status": status, "financial_acceptance": False}))
            raise SystemExit(2) from None
        return
    if args.command == "sec-directory":
        if not args.user_agent:
            parser.error("SEC_USER_AGENT or --user-agent with identifying contact is required")
        try:
            transport = HttpTransport(user_agent=args.user_agent, allowed_hosts={"www.sec.gov"})
            snapshot = SecDirectory(transport).fetch()
            matches = []
            for symbol in args.symbol:
                entry = snapshot.lookup(symbol)
                matches.append({"symbol": symbol, "cik": entry.issuer.cik if entry else None,
                                "status": "identity_found" if entry else "identity_not_found"})
        except (ProviderFailure, ValueError) as exc:
            status = exc.status.value if isinstance(exc, ProviderFailure) else "invalid_configuration"
            print(json.dumps({"status": status, "source": "SEC", "financial_acceptance": False}))
            raise SystemExit(2) from None
        print(json.dumps({"source_url": snapshot.source_url, "sha256": snapshot.sha256,
                          "retrieved_at": snapshot.retrieved_at.isoformat(),
                          "directory_entries": len(snapshot.entries), "matches": matches,
                          "active_common_share_universe_verified": False,
                          "financial_acceptance": False}, indent=2))
        return
    print(json.dumps({"version": __version__, "stage": "identity_adapter", "live_providers": [],
                      "implemented_identity_adapters": ["SEC"],
                      "implemented_financial_adapters": ["Yahoo assets only", "SEC", "Nasdaq assets and liabilities", "Finnhub reported contracts; live unverified"],
                      "implemented_discovery_adapters": ["Nasdaq screener"],
                      "real_companies_validated": 0, "score_weights": dict(SCORE_WEIGHTS),
                      "production_accepted": False}, indent=2))


if __name__ == "__main__":
    main()
