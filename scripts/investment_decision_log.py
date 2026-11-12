"""Private append-only investment thesis journal; no trades or autonomous learning.

Use a local path OUTSIDE the public repository for real user holdings or decisions.
A verified result is an observation, not proof of predictive skill.
"""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

ACTIONS = {"AL", "TUT", "AZALT", "SAT", "BEKLE", "INCELE"}
MARKETS = {"ABD", "BIST", "AVRUPA"}
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,18}$")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def verify_log(events):
    previous = "0" * 64
    ids = set()
    if not isinstance(events, list):
        raise ValueError("journal must contain a list")
    for index, row in enumerate(events):
        if not isinstance(row, dict) or row.get("index") != index:
            raise ValueError("journal order invalid")
        if row.get("previous_sha256") != previous:
            raise ValueError("journal history changed")
        body = {k: v for k, v in row.items() if k != "sha256"}
        digest = hashlib.sha256(canonical(body).encode()).hexdigest()
        if digest != row.get("sha256"):
            raise ValueError("journal record tampered")
        event = row.get("event")
        if event not in ("thesis", "outcome"):
            raise ValueError("unknown journal event")
        if event == "thesis":
            if row["decision_id"] in ids:
                raise ValueError("duplicate investment decision")
            ids.add(row["decision_id"])
        else:
            if row["decision_id"] not in ids:
                raise ValueError("outcome cannot precede decision")
        previous = digest
    return previous


def validate_event(payload):
    if not isinstance(payload, dict) or payload.get("event") not in ("thesis", "outcome"):
        raise ValueError("thesis/outcome event required")
    if not isinstance(payload.get("decision_id"), str) or not re.fullmatch(
        r"[a-zA-Z0-9_.\-]{8,90}", payload["decision_id"]
    ):
        raise ValueError("stable decision identifier required")
    timestamp = datetime.fromisoformat(payload["as_of"])
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timezone-aware decision date required")
    if payload["event"] == "thesis":
        if (payload.get("action") not in ACTIONS or payload.get("market") not in MARKETS
                or not isinstance(payload.get("symbol"), str)
                or not SYMBOL.fullmatch(payload["symbol"])
                or not isinstance(payload.get("rationale"), str)
                or len(payload["rationale"].strip()) < 20
                or not isinstance(payload.get("invalidation"), str)
                or len(payload["invalidation"].strip()) < 10
                or payload.get("participation_status") not in ("eligible", "ineligible", "unknown")):
            raise ValueError("complete and falsifiable thesis required")
        if (payload["action"] == "AL" and payload["participation_status"] != "eligible"):
            raise ValueError("unverified participation cannot receive buy approval")
    else:
        if (payload.get("result") not in ("correct", "incorrect", "inconclusive")
                or not isinstance(payload.get("evidence_url"), str)
                or not payload["evidence_url"].startswith("https://")
                or not isinstance(payload.get("analysis"), str)
                or len(payload["analysis"].strip()) < 20):
            raise ValueError("source-backed outcome review required")


def append_event(journal_path, event):
    validate_event(event)
    original = Path(journal_path)
    if original.is_symlink():
        raise ValueError("symlink journal not accepted")
    journal = original.resolve()
    if journal.is_file():
        events = json.loads(journal.read_text(encoding="utf-8"))
    else:
        events = []
    previous = verify_log(events)
    if event["event"] == "thesis" and any(
        x["event"] == "thesis" and x["decision_id"] == event["decision_id"] for x in events
    ):
        raise ValueError("decision already recorded")
    if event["event"] == "outcome" and not any(
        x["event"] == "thesis" and x["decision_id"] == event["decision_id"] for x in events
    ):
        raise ValueError("decision required before outcome")
    row = dict(event, index=len(events), previous_sha256=previous)
    row["sha256"] = hashlib.sha256(canonical(row).encode()).hexdigest()
    events.append(row)
    journal.parent.mkdir(parents=True, exist_ok=True)
    temporary = journal.with_suffix(journal.suffix + ".tmp")
    temporary.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, journal)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True, help="PRIVATE local path; never public GitHub")
    parser.add_argument("--event", required=True, help="JSON event file, not an account credential")
    args = parser.parse_args()
    if Path(args.journal).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("real investment decisions must be stored outside public repo")
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    row = append_event(args.journal, event)
    print(json.dumps({"index": row["index"], "sha256": row["sha256"]}))


if __name__ == "__main__":
    main()
