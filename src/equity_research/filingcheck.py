"""Narrow independent iXBRL balance-sheet check; no general filing parser claim."""
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from .concept_diagnostics import inspect_concepts
from .providers import ProviderFailure, Status


LIABILITY_EQUATION_CONCEPTS = (
    "us-gaap:Liabilities",
    "us-gaap:Assets",
    "us-gaap:LiabilitiesAndStockholdersEquity",
    "us-gaap:StockholdersEquity",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "us-gaap:MinorityInterest",
    "us-gaap:TemporaryEquityCarryingAmount",
    "us-gaap:RedeemableNoncontrollingInterestEquityCarryingAmount",
    "us-gaap:NoncontrollingInterestInConsolidatedEntity",
)


class AssetsParser(HTMLParser):
    def __init__(self,concept="Assets"):
        super().__init__(convert_charrefs=True)
        self.contexts, self.numbers = {}, []
        self.context, self.capture, self.number = None, None, None
        self.concept=concept

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        local = tag.rsplit(":", 1)[-1]
        if local == "context":
            self.context = {"id": attrs.get("id"), "dimensional": False}
        elif self.context is not None:
            if local in ("segment", "scenario", "explicitmember", "typedmember"):
                self.context["dimensional"] = True
            if local in ("identifier", "instant"):
                self.capture = local
                self.context[local] = ""
                if local == "identifier":
                    self.context["scheme"] = attrs.get("scheme")
        if local == "nonfraction" and attrs.get("name", "").lower() == "us-gaap:"+self.concept.lower():
            self.number = {"attrs": attrs, "text": ""}

    def handle_data(self, data):
        if self.context is not None and self.capture:
            self.context[self.capture] += data
        if self.number is not None:
            self.number["text"] += data

    def handle_endtag(self, tag):
        local = tag.rsplit(":", 1)[-1]
        if local == "context" and self.context is not None:
            self.contexts[self.context["id"]] = self.context
            self.context, self.capture = None, None
        elif local in ("identifier", "instant"):
            self.capture = None
        if local == "nonfraction" and self.number is not None:
            self.numbers.append(self.number)
            self.number = None


def filing_instant(body: bytes, *, cik: str, period_end: date, concept: str) -> Decimal:
    """Require one unambiguous non-dimensional USD instant fact for exact date."""
    try:
        if concept not in ("Assets","Liabilities"):raise ValueError("unsupported instant concept")
        parser = AssetsParser(concept)
        parser.feed(body.decode("utf-8"))
        values = set()
        # Unit IDs are arbitrary. Inspect the declared unit instead of guessing
        # that unitref='usd' is sufficient evidence of currency.
        class Units(HTMLParser):
            def __init__(self):
                super().__init__();self.units={};self.uid=None;self.capture=False
            def handle_starttag(self,tag,attrs):
                local=tag.rsplit(":",1)[-1]
                if local=="unit":self.uid=dict(attrs).get("id");self.units[self.uid]=""
                elif local=="measure" and self.uid is not None:self.capture=True
                elif local in ("divide","unitnumerator","unitdenominator") and self.uid is not None:self.units[self.uid]+="compound:"
            def handle_data(self,data):
                if self.capture:self.units[self.uid]+=data.strip()
            def handle_endtag(self,tag):
                local=tag.rsplit(":",1)[-1]
                if local=="unit":self.uid=None
                elif local=="measure":self.capture=False
        units=Units();units.feed(body.decode("utf-8"))
        for number in parser.numbers:
            attrs=number["attrs"]
            context=parser.contexts.get(attrs.get("contextref"),{})
            if (context.get("instant") != period_end.isoformat() or context.get("dimensional")
                    or context.get("identifier", "").strip().lstrip("0") != cik.lstrip("0")
                    or context.get("scheme") != "http://www.sec.gov/CIK"
                    or units.units.get(attrs.get("unitref")) != "iso4217:USD"):
                continue
            if attrs.get("xsi:nil", "false").lower() == "true":
                continue
            # Only standard nonnegative numeric presentation is supported here.
            # Unsupported transforms/continuations fail rather than guess.
            if attrs.get("continuedat") or attrs.get("sign") not in (None,"-"):
                raise ValueError("unsupported number presentation")
            if attrs.get("format") and attrs["format"].lower().rsplit(":",1)[-1] not in ("num-dot-decimal", "numdotdecimal"):
                raise ValueError("unsupported numeric transform")
            text=number["text"].replace(",", "").strip()
            scale=int(attrs.get("scale", "0"))
            if not -12 <= scale <= 12:
                raise ValueError("unsupported scale")
            value=Decimal(text)*(Decimal(10)**scale)
            if attrs.get("sign")=="-":value=-value
            if not value.is_finite():raise ValueError("nonfinite number")
            values.add(value)
        if len(values)!=1:
            raise ValueError("absent or conflicting filing evidence")
        return values.pop()
    except (ValueError, TypeError, UnicodeError, InvalidOperation):
        raise ProviderFailure(Status.INVALID_DATA) from None


def filing_assets(body: bytes, *, cik: str, period_end: date) -> Decimal:
    return filing_instant(body,cik=cik,period_end=period_end,concept="Assets")


def filing_derived_liabilities(body: bytes, *, cik: str, period_end: date) -> dict:
    """Prove liabilities from one exact original-filing balance equation.

    This is an independent confirmation of an already selected liabilities
    value, not a provider alias or a replacement SEC fact. It rejects missing
    total-equity scope, unexplained noncontrolling interest and mezzanine equity.
    """
    try:
        scan=inspect_concepts(body,cik=cik,concepts=LIABILITY_EQUATION_CONCEPTS,
            period_start=None,period_end=period_end)
        facts={row['concept']:row for row in scan['concepts']}
        def exact(name):
            row=facts[name]
            return Decimal(row['value']) if row['status']=='exact_original_value' else None
        liabilities=facts['us-gaap:Liabilities']
        if liabilities['status'] not in ('concept_not_disclosed','period_or_scope_mismatch'):
            raise ValueError('literal liabilities is not a clean fallback case')
        assets=exact('us-gaap:Assets');combined=exact('us-gaap:LiabilitiesAndStockholdersEquity')
        common_equity=exact('us-gaap:StockholdersEquity')
        total_equity=exact('us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest')
        minority=exact('us-gaap:MinorityInterest')
        if assets is None or combined is None or common_equity is None or assets!=combined or assets<0:
            raise ValueError('balance equation totals do not reconcile')
        excluded=[]
        for name in ('us-gaap:TemporaryEquityCarryingAmount',
                     'us-gaap:RedeemableNoncontrollingInterestEquityCarryingAmount',
                     'us-gaap:NoncontrollingInterestInConsolidatedEntity'):
            row=facts[name];value=exact(name)
            if row['status'] not in ('concept_not_disclosed','period_or_scope_mismatch','exact_original_value'):
                raise ValueError('unresolved excluded equity scope')
            if value not in (None,Decimal(0)):
                raise ValueError('mezzanine or separate noncontrolling interest requires review')
            excluded.append(dict(concept=name,status=row['status'],value=row['value']))
        if total_equity is None:
            if minority not in (None,Decimal(0)):
                raise ValueError('minority interest is outside selected equity scope')
            equity=common_equity;equity_concept='us-gaap:StockholdersEquity'
        else:
            if minority is None:
                if total_equity!=common_equity:raise ValueError('total equity cannot be decomposed')
            elif common_equity+minority!=total_equity:
                raise ValueError('stockholder and minority equity do not reconcile')
            equity=total_equity
            equity_concept='us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
        value=combined-equity
        if value<0:raise ValueError('negative derived liabilities')
        operands=[dict(concept='us-gaap:LiabilitiesAndStockholdersEquity',value=str(combined)),
                  dict(concept=equity_concept,value=str(equity))]
        if equity_concept.endswith('NoncontrollingInterest'):
            operands.extend((dict(concept='us-gaap:StockholdersEquity',value=str(common_equity)),
                             dict(concept='us-gaap:MinorityInterest',value=str(minority))))
        return dict(value=str(value),currency='USD',period_end=period_end.isoformat(),
            formula='LiabilitiesAndStockholdersEquity - total_equity',operands=operands,
            literal_liabilities_status=liabilities['status'],excluded_scope_checks=excluded,
            raw_sha256=scan['raw_sha256'],automatic_substitution=False,scope_approved=False)
    except (ValueError,TypeError,KeyError,InvalidOperation):
        raise ProviderFailure(Status.INVALID_DATA) from None
