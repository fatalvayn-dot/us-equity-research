"""BIST/European public-source discovery and ECB reference-rate diagnostics.

This *does not collect* price feeds, parse company accounts or make a score.
All facts are unverified until an individual original filing, issuer identity,
publication time and licensed price source have separately passed review.
"""
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
from io import StringIO
from urllib.parse import urlsplit


# Verified public landing pages, not primary original financial-report evidence.
# Changes require independent issuer and document-link review.
SOURCE_PROBES = {
    ("BIST", "ASELS"): {
        "issuer": "ASELSAN ELEKTRONIK SANAYI VE TICARET A.S.",
        "currency": "TRY",
        "source_kind": "kap_issuer_profile",
        "url": "https://kap.org.tr/tr/sirket-bilgileri/ozet/866-aselsan-elektronik-sanayi-ve-ticaret-a-s",
    },
    ("BIST", "TUPRS"): {
        "issuer": "TUPRAS TURKIYE PETROL RAFINERILERI A.S.",
        "currency": "TRY",
        "source_kind": "kap_issuer_profile",
        "url": "https://www.kap.org.tr/tr/sirket-bilgileri/ozet/1105-tupras-turkiye-petrol-rafinerileri-a-s",
    },
    ("BIST", "BIMAS"): {
        "issuer": "BIM BIRLESIK MAGAZALAR A.S.",
        "currency": "TRY",
        "source_kind": "kap_issuer_profile",
        "url": "https://www.kap.org.tr/tr/sirket-bilgileri/ozet/4028e4a140e95be70140ee1b7b030119",
    },
    ("XETRA", "SAP"): {
        "issuer": "SAP SE",
        "currency": "EUR",
        "source_kind": "issuer_investor_relations",
        "url": "https://www.sap.com/investors/en.html",
    },
    ("XETRA", "IFX"): {
        "issuer": "Infineon Technologies AG",
        "currency": "EUR",
        "source_kind": "issuer_investor_relations",
        "url": "https://www.infineon.com/about/investor",
    },
    ("XETRA", "DTE"): {
        "issuer": "Deutsche Telekom AG",
        "currency": "EUR",
        "source_kind": "issuer_annual_report_portal",
        "url": "https://report.telekom.com/annual-report-2025/",
    },
}
ECB_KEYS = {
    "USD": "EXR.D.USD.EUR.SP00.A",
    "TRY": "EXR.D.TRY.EUR.SP00.A",
}


def _aware(value):
    if not isinstance(value, str):
        raise ValueError("timezone-aware ISO timestamp required")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid ISO timestamp") from None
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return instant


def _exact_url(value, allowed_host):
    if not isinstance(value, str):
        raise ValueError("absolute HTTPS source URL required")
    u = urlsplit(value)
    if (u.scheme != "https" or u.hostname != allowed_host
            or u.username is not None or u.password is not None
            or u.port is not None or u.fragment or u.query):
        raise ValueError("untrusted or transformed source URL")
    return value


def audit_regional_discovery(market, symbol, source_url, *, observed_at, as_of):
    """Check exact known public landing-page identity; no financial fact accepted."""
    if (market, symbol) not in SOURCE_PROBES:
        raise ValueError("issuer is outside the reviewed six-company research sample")
    source = SOURCE_PROBES[(market, symbol)]
    _exact_url(source_url, urlsplit(source["url"]).hostname)
    if source_url != source["url"]:
        raise ValueError("issuer source URL differs from reviewed address")
    if _aware(observed_at) > _aware(as_of):
        raise ValueError("source observation is from the future")
    return {
        "market": market,
        "symbol": symbol,
        "issuer": source["issuer"],
        "reporting_currency_candidate": source["currency"],
        "source_url": source_url,
        "source_kind": source["source_kind"],
        "observed_at": observed_at,
        "decision": "source_discovery_only",
        "financial_facts_verified": 0,
        "security_class_verified": False,
        "issuer_identifier_verified": False,
        "publication_time_verified": False,
        "historical_price_licensed": False,
        "shariah_approved": False,
        "investment_approved": False,
    }


def audit_ecb_reference_csv(raw, *, currency, observed_at, as_of):
    """Fail-closed ECB SDMX CSV inspection; NOT an execution FX quote.

    Original HTTP response bytes must be supplied by caller; the hash is
    for *these supplied bytes*, not proof of remote authenticity.
    ECB daily observations are not guaranteed published at the start of
    TIME_PERIOD: an independent publication timestamp is still required.
    """
    if currency not in ECB_KEYS:
        raise ValueError("only USD/TRY ECB euro reference series supported")
    if type(raw) is not bytes or not raw or len(raw) > 2_000_000:
        raise ValueError("bounded original CSV bytes required")
    if _aware(observed_at) > _aware(as_of):
        raise ValueError("ECB file observed after decision")
    try:
        content = raw.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(content))
        if reader.fieldnames is None or not {"KEY", "TIME_PERIOD", "OBS_VALUE"}.issubset(reader.fieldnames):
            raise ValueError("ECB SDMX CSV columns missing")
        rows = []
        seen = set()
        for row in reader:
            if row["KEY"] != ECB_KEYS[currency]:
                raise ValueError("ECB series key or base currency mismatch")
            stamp = date.fromisoformat(row["TIME_PERIOD"])
            if stamp.isoformat() != row["TIME_PERIOD"] or stamp > _aware(as_of).date():
                raise ValueError("future/noncanonical ECB observation date")
            if stamp in seen:
                raise ValueError("duplicate ECB date")
            seen.add(stamp)
            if row.get("OBS_STATUS") not in (None, "", "A"):
                raise ValueError("unverified ECB observation status")
            rate = Decimal(row["OBS_VALUE"])
            if not rate.is_finite() or rate <= 0:
                raise ValueError("positive finite ECB rate required")
            rows.append({"period": stamp.isoformat(), "currency_per_eur": str(rate)})
    except (UnicodeError, InvalidOperation, TypeError, KeyError):
        raise ValueError("invalid ECB CSV evidence") from None
    if not rows:
        raise ValueError("no ECB rate observations")
    return {
        "provider": "ECB_EXR_reference",
        "currency": currency,
        "base_currency": "EUR",
        "reference_rates": rows,
        "raw_supplied_sha256": hashlib.sha256(raw).hexdigest(),
        "observed_at": observed_at,
        "decision": "publication_time_and_trading_rate_review_required",
        "not_executable_broker_fx": True,
        "investment_approved": False,
    }
