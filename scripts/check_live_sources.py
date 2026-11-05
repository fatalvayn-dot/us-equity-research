"""Uzun canlı taramadan önce açık veri adreslerine erişimi ölç."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from equity_research.companyfacts import companyfacts_url
from equity_research.mvp import save_json
from equity_research.nasdaq import DIRECTORY_ENDPOINTS
from equity_research.prices import price_url
from equity_research.providers import ProviderFailure
from equity_research.sec import DIRECTORY_URL
from equity_research.submissions import submissions_url
from equity_research.transport import HttpTransport, RateLimiter

SOURCES = (
    ("sec_identity", (DIRECTORY_URL,)),
    ("sec_submissions", (submissions_url("0000320193"),)),
    ("sec_companyfacts", (companyfacts_url("0000320193"),)),
    ("yahoo_price", (price_url("AAPL"),)),
    ("nasdaq_listed", DIRECTORY_ENDPOINTS["nasdaqlisted"]),
    ("nasdaq_other_listed", DIRECTORY_ENDPOINTS["otherlisted"]),
)


def check(user_agent):
    sec_limiter = RateLimiter()
    started_at = datetime.now(timezone.utc)

    def probe(source):
        name, urls = source
        attempts = []
        for url in urls:
            host = urlsplit(url).hostname
            client = HttpTransport(
                user_agent=user_agent,
                allowed_hosts={host},
                limiter=sec_limiter if host.endswith(".sec.gov") else None,
                # SEC endpoints sometimes need longer to establish a
                # connection; keep a strict per-source total deadline.
                timeout=12 if host.endswith(".sec.gov") else 5,
                budget=16 if host.endswith(".sec.gov") else 8,
                max_attempts=1,
                accept="text/plain" if name.startswith("nasdaq_") else "application/json",
            )
            try:
                response = client.get(url)
            except ProviderFailure as exc:
                attempts.append({
                    "url": url,
                    "status": exc.status.value,
                    "http_status": exc.http_status,
                    "reason": exc.reason.value if exc.reason else None,
                })
            else:
                attempts.append({
                    "url": response.url,
                    "status": "response_received",
                    "retrieved_at": response.retrieved_at.isoformat(),
                    "sha256": response.sha256,
                    "bytes": len(response.body),
                })
                return {"source": name, "reachable": True, "attempts": attempts}
        return {"source": name, "reachable": False, "attempts": attempts}

    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = list(pool.map(probe, SOURCES))
    return {
        "kind": "transport_preflight",
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "reachable_sources": sum(source["reachable"] for source in sources),
        "sources_checked": len(sources),
        "companies_validated": 0,
        "mvp_accepted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.user_agent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_json(args.output, report)
    print(json.dumps({
        "erişilen_kaynak": report["reachable_sources"],
        "kontrol_edilen_kaynak": report["sources_checked"],
        "kanıt_dosyası": str(args.output),
    }, ensure_ascii=False))
    return int(report["reachable_sources"] != report["sources_checked"])


if __name__ == "__main__":
    raise SystemExit(main())
