"""Evidence-gated, non-certifying participation-screen research.

This module intentionally defines NO Shariah financial-ratio thresholds.
Different index standards use different bases, scopes and effective dates.
Even a full conditional screen pass is NOT a buy recommendation, an index
membership claim, an authoritative ruling or investment approval.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit

from .sector_policy import excluded_banking_or_insurance


RULES = ("interest_debt", "interest_cash_securities", "impermissible_income")
ISSUER_ID = re.compile(r"(?:SEC:[0-9]{10}|KAP:[A-Za-z0-9_-]{1,40}|LEI:[A-Z0-9]{20})\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timezone-aware publication timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid ISO timestamp") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return stamp.astimezone(timezone.utc)


def _decimal(value, *, allow_zero=True, upper=None):
    if type(value) not in (str, int, Decimal):
        raise ValueError("explicit decimal string or integer required")
    try:
        out = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("invalid decimal") from None
    if not out.is_finite() or out < 0 or (not allow_zero and out == 0):
        raise ValueError("invalid finite nonnegative ratio operand")
    if upper is not None and out > upper:
        raise ValueError("ratio threshold outside allowed range")
    return out


def _source(source, *, as_of, issuer_key=None, period_end=None):
    if not isinstance(source, dict):
        raise ValueError("original-source proof missing")
    url = source.get("url")
    if not isinstance(url, str):
        raise ValueError("original HTTPS source URL required")
    split = urlsplit(url)
    if (split.scheme != "https" or not split.hostname or split.username is not None
            or split.password is not None or split.port is not None
            or split.fragment or split.hostname in ("localhost", "127.0.0.1")):
        raise ValueError("invalid original source URL")
    if issuer_key is not None and source.get("issuer_key") != issuer_key:
        raise ValueError("source issuer identity mismatch")
    if not isinstance(source.get("raw_sha256"), str) or not SHA.fullmatch(source["raw_sha256"]):
        raise ValueError("original source content SHA-256 reference missing")
    pub = _timestamp(source.get("published_at"))
    seen = _timestamp(source.get("retrieved_at"))
    if pub > seen or seen > as_of:
        raise ValueError("unavailable or future source evidence")
    if period_end is not None and pub.date() < period_end:
        raise ValueError("report published before its period ended")
    return dict(url=url, raw_sha256=source["raw_sha256"],
                published_at=pub.isoformat(), retrieved_at=seen.isoformat())


def _rulebook(rulebook, *, cutoff):
    if not isinstance(rulebook, dict):
        raise ValueError("participation standard not selected")
    if (not isinstance(rulebook.get("standard_id"), str) or not rulebook["standard_id"].strip()
            or not isinstance(rulebook.get("version"), str) or not rulebook["version"].strip()
            or rulebook.get("reviewed") is not True):
        raise ValueError("versioned reviewed standard required")
    _source(rulebook.get("source"), as_of=cutoff)
    effective = date.fromisoformat(rulebook["effective_from"])
    if effective > cutoff.date():
        raise ValueError("future-dated standard")
    days = rulebook.get("max_statement_age_days")
    if type(days) is not int or not 1 <= days <= 730:
        raise ValueError("bounded source freshness policy required")
    rules = rulebook.get("ratios")
    if not isinstance(rules, dict) or set(rules) != set(RULES):
        raise ValueError("all three explicitly defined ratio rules required")
    parsed = {}
    for name in RULES:
        r = rules[name]
        if (not isinstance(r, dict) or not isinstance(r.get("numerator_definition"), str)
                or not r["numerator_definition"].strip()
                or not isinstance(r.get("denominator_definition"), str)
                or not r["denominator_definition"].strip()):
            raise ValueError("exact numerator/denominator definitions required")
        parsed[name] = (r["numerator_definition"], r["denominator_definition"],
                        _decimal(r.get("max_ratio"), upper=Decimal(1)))
    return parsed, days


def _ratio(name, raw, rule, *, cutoff, issuer_key, freshness_days):
    if not isinstance(raw, dict):
        raise ValueError("missing ratio source facts")
    numerator_definition, denominator_definition, limit = rule
    if (raw.get("numerator_definition") != numerator_definition
            or raw.get("denominator_definition") != denominator_definition):
        raise ValueError("ratio accounting/market denominator definition mismatch")
    period = date.fromisoformat(raw["period_end"])
    if period > cutoff.date() or (cutoff.date() - period).days > freshness_days:
        raise ValueError("statement period missing, future or stale")
    if not isinstance(raw.get("currency"), str) or not re.fullmatch(r"[A-Z]{3}", raw["currency"]):
        raise ValueError("ratio currency unit not provided")
    numerator = _decimal(raw.get("numerator"))
    denominator = _decimal(raw.get("denominator"), allow_zero=False)
    src1 = _source(raw.get("numerator_source"), as_of=cutoff,
                   issuer_key=issuer_key, period_end=period)
    src2 = _source(raw.get("denominator_source"), as_of=cutoff,
                   issuer_key=issuer_key, period_end=period)
    ratio = numerator / denominator
    return {"ratio": str(ratio), "max_ratio": str(limit), "pass": ratio <= limit,
            "currency": raw["currency"], "period_end": period.isoformat(),
            "numerator_evidence": src1, "denominator_evidence": src2}


def assess_participation(company, rulebook=None, *, as_of):
    """Produce tri-state *research* status, with every buy/certification gate off.

    Status values:
      uygunsuz: independently evidenced excluded business/financial ratio;
      bilinmiyor: missing, expired or conflicting evidence;
      kosullu_esik_gecisi: the supplied *reviewed* method's stated tests pass.
    """
    cutoff = _timestamp(as_of)
    if not isinstance(company, dict):
        raise ValueError("issuer evidence required")
    issuer_key, symbol = company.get("issuer_key"), company.get("symbol")
    if (not isinstance(issuer_key, str) or not ISSUER_ID.fullmatch(issuer_key)
            or not isinstance(symbol, str) or not symbol or symbol.strip() != symbol):
        raise ValueError("exact exchange issuer identity and symbol required")

    reasons = []
    blockers = []
    ratios = {}
    sector = company.get("sector") if isinstance(company.get("sector"), dict) else {}
    industry = sector.get("industry")
    sic = sector.get("sec_sic")
    if sic is not None and (not isinstance(sic, str) or
                            not re.fullmatch(r"[0-9]{4}", sic)):
        reasons.append("invalid_sec_sic")
    if industry in ("banking", "insurance") or excluded_banking_or_insurance(sic):
        blockers.append("permanent_banking_insurance_exclusion")
    try:
        _source(sector.get("source"), as_of=cutoff, issuer_key=issuer_key)
        if industry not in ("banking", "insurance", "nonfinancial"):
            reasons.append("unknown_sector_classification")
        if industry == "nonfinancial" and excluded_banking_or_insurance(sic):
            reasons.append("conflicting_sector_evidence")
    except (ValueError, TypeError):
        reasons.append("sector_evidence_unverified")

    instrument = company.get("instrument_type")
    if instrument != "common_share":
        reasons.append("special_instrument_review_required")

    activity = company.get("activities") if isinstance(company.get("activities"), dict) else {}
    try:
        _source(activity.get("source"), as_of=cutoff, issuer_key=issuer_key)
        if activity.get("conclusion") == "prohibited":
            blockers.append("prohibited_business_activity")
        elif activity.get("conclusion") != "permitted":
            reasons.append("unreviewed_business_activity")
    except (ValueError, TypeError):
        reasons.append("business_activity_evidence_unverified")

    rules = None
    freshness = None
    try:
        rules, freshness = _rulebook(rulebook, cutoff=cutoff)
    except (ValueError, KeyError, TypeError):
        reasons.append("reviewed_standard_evidence_missing")

    facts = company.get("ratios") if isinstance(company.get("ratios"), dict) else {}
    if rules is not None:
        for name in RULES:
            try:
                result = _ratio(name, facts.get(name), rules[name], cutoff=cutoff,
                                issuer_key=issuer_key, freshness_days=freshness)
                ratios[name] = result
                if not result["pass"]:
                    blockers.append(name + "_exceeds_standard_threshold")
            except (ValueError, TypeError, KeyError, ArithmeticError):
                reasons.append(name + "_unverified_or_incompatible")

    if blockers:
        status = "uygunsuz"
    elif reasons:
        status = "bilinmiyor"
    else:
        status = "kosullu_esik_gecisi"
    return dict(
        issuer_key=issuer_key, symbol=symbol, as_of=cutoff.isoformat(),
        status=status, rulebook_id=rulebook.get("standard_id") if isinstance(rulebook, dict) else None,
        rulebook_version=rulebook.get("version") if isinstance(rulebook, dict) else None,
        blockers=sorted(set(blockers)), review_reasons=sorted(set(reasons)),
        ratios=ratios, evidence_scope="provided_sources_syntactic_validation_only",
        qualified_for_investment=False, shariah_certified=False,
        investment_approved=False, eligible_for_automatic_order=False,
        no_live_source_verification=True,
    )
