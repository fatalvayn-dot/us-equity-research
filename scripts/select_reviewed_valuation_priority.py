"""Return a reviewed valuation priority plan only for its exact input artifacts."""
import argparse
import hashlib
import json
from pathlib import Path


def select(plan, source_run, resume_run, resume_report):
    reviewed = json.loads(plan.read_text())
    if (reviewed['financial_run_id'], reviewed['valuation_run_id']) != (source_run, resume_run):
        return None
    with resume_report.open('rb') as report:
        actual = hashlib.file_digest(report, 'sha256').hexdigest()
    if actual != reviewed['valuation_report_sha256']:
        raise ValueError('reviewed valuation continuation report digest mismatch')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--source-run', type=int, required=True)
    parser.add_argument('--resume-run', type=int)
    parser.add_argument('--resume-report', type=Path, required=True)
    args = parser.parse_args()
    plan = select(**vars(args))
    if plan is not None:
        print(plan)


if __name__ == '__main__':
    main()
