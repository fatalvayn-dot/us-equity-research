"""CLI for the append-only advice ledger (data/analyst/advice_ledger.jsonl)."""
import argparse
import json
import sys
from pathlib import Path

from equity_research import advice_ledger as L

DEFAULT = Path(__file__).resolve().parents[1] / 'data' / 'analyst' / 'advice_ledger.jsonl'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', default=str(DEFAULT))
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('add');a.add_argument('--json', required=True, help='advice fields as JSON object')
    e = sub.add_parser('evaluate');e.add_argument('--json', required=True)
    r = sub.add_parser('review');r.add_argument('--json', required=True)
    sub.add_parser('report');sub.add_parser('verify')
    args = ap.parse_args(argv)
    if args.cmd == 'add':
        out = L.record_advice(args.ledger, **json.loads(args.json))
    elif args.cmd == 'evaluate':
        d = json.loads(args.json);out = L.evaluate(args.ledger, d.pop('advice_id'), **d)
    elif args.cmd == 'review':
        d = json.loads(args.json);out = L.review(args.ledger, d.pop('advice_id'), **d)
    elif args.cmd == 'verify':
        out = dict(chain_ok=True, head=L.verify_chain(L.read(args.ledger)))
    else:
        out = L.calibration(args.ledger)
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr);sys.exit(1)
