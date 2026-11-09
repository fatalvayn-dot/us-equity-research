"""Audit class-specific SEC share disclosures without feeding valuation."""
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from equity_research.concept_diagnostics import Inventory
from equity_research.filing_metadata import filing_security_metadata
from equity_research.valuation import SHARE_CONCEPT, _share_number


class ClassInventory(Inventory):
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if self.context is None:
            return
        if tag == "xbrldi:explicitmember":
            self.capture = "explicit_member"
            self.context.setdefault("members", []).append([dict(attrs).get("dimension"), ""])
        elif tag.rsplit(":", 1)[-1] == "typedmember":
            self.context["typed_member"] = True

    def handle_data(self, data):
        if self.capture == "explicit_member":
            self.context["members"][-1][1] += data
        else:
            super().handle_data(data)

    def handle_endtag(self, tag):
        if tag == "xbrldi:explicitmember":
            self.capture = None
        super().handle_endtag(tag)


def audit(body, *, cik, symbol, report_end, document_type, sha256):
    if hashlib.sha256(body).hexdigest() != sha256:
        raise ValueError("SEC belge SHA-256 uyuşmuyor")
    cover = filing_security_metadata(body, cik=cik, symbol=symbol, report_end=report_end,
                                     document_type=document_type)
    title = cover["registered_security"][0]["title"]
    listed_class = re.search(r"\bClass ([A-Za-z0-9]+) (?:Common Stock|Ordinary Shares?)\b",
                             title, re.I)
    if listed_class is None:
        raise ValueError("Borsada kayıtlı hisse sınıfı kapakta açık olmalıdır")
    parser = ClassInventory()
    parser.feed(body.decode("utf-8"))
    parser.close()
    if (parser.conflict or parser.context is not None or parser.unit is not None or parser.stack
            or parser.namespaces.get("xbrldi") != "http://xbrl.org/2006/xbrldi"
            or not re.fullmatch(r"http://fasb.org/us-gaap/20[0-9]{2}", parser.namespaces.get("us-gaap", ""))):
        raise ValueError("SEC hisse boyutu taksonomisi doğrulanamadı")

    counts = {}
    for fact in parser.facts:
        if fact["attrs"].get("name", "").lower() != SHARE_CONCEPT.lower():
            continue
        context_id = fact["attrs"].get("contextref")
        context = parser.contexts.get(context_id, {})
        members = context.get("members", [])
        if (context.get("scheme") != "http://www.sec.gov/CIK"
                or context.get("identifier", "").strip().zfill(10) != cik
                or not context.get("instant") or context.get("startdate") or context.get("enddate")
                or context.get("typed_member") or len(members) != 1 or members[0][0] != "us-gaap:StatementClassOfStockAxis"):
            raise ValueError("Tek ve açık hisse sınıfı bağlamı gerekli")
        member = members[0][1].strip()
        prefix, separator, local = member.partition(":")
        if not separator or not parser.namespaces.get(prefix) or not re.fullmatch(r"CommonClass[A-Za-z0-9]+Member", local):
            raise ValueError("Adi hisse sınıfı üyesi doğrulanamadı")
        disclosed_on = date.fromisoformat(context["instant"].strip()).isoformat()
        key = (disclosed_on, parser.namespaces[prefix], local)
        if key in counts:
            raise ValueError("Tekrarlı hisse sınıfı bildirimi")
        value, decimals = _share_number(fact, parser)
        counts[key] = dict(context_id=context_id, member=member, member_namespace=key[1],
                           disclosed_on=disclosed_on, shares=int(value), decimals=decimals)
    if len(counts) < 2 or len({key[0] for key in counts}) != 1:
        raise ValueError("Aynı tarihe ait birden çok sınıf bildirimi gerekli")
    listed_member = f"CommonClass{listed_class.group(1)}Member".casefold()
    listed_counts = [value for key, value in counts.items() if key[2].casefold() == listed_member]
    if len(listed_counts) != 1:
        raise ValueError("Borsada kayıtlı hisse sınıfının sayımı tekil olmalıdır")
    return dict(cover=cover, class_counts=list(counts.values()),
                listed_class_member=listed_counts[0]["member"],
                valuation_eligible=False, scope_approved=False, mvp_accepted=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filing", type=Path)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--report-end", type=date.fromisoformat, required=True)
    parser.add_argument("--document-type", required=True)
    parser.add_argument("--sha256", required=True)
    args = vars(parser.parse_args())
    print(json.dumps(audit(args.pop("filing").read_bytes(), **args), ensure_ascii=False, indent=2))
