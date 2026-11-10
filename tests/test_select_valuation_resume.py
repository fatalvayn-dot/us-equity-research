import os
import runpy
import unittest
from unittest.mock import patch

from scripts.select_valuation_resume import (
    AUDITED_RUN, COLLECTION_STEP, REVIEWED_STARTUP_FAILURE, main_runs, select,
)


def run(offset, *, status="completed", conclusion="success"):
    return dict(id=AUDITED_RUN + offset, status=status, conclusion=conclusion,
                head_branch="main")


def artifact(**kwargs):
    return dict(name="valuation-source-state", expired=False) | kwargs


class ValuationResumeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.responses = {}

    def fetch(self, path):
        return self.responses[path]

    def artifacts(self, offset, *items):
        self.responses[f"actions/runs/{AUDITED_RUN + offset}/artifacts?per_page=100"] = {
            "total_count": len(items), "artifacts": list(items),
        }

    def jobs(self, offset, *conclusions):
        self.responses[f"actions/runs/{AUDITED_RUN + offset}/jobs?filter=all&per_page=100"] = {
            "total_count": len(conclusions),
            "jobs": [{"steps": [{"name": COLLECTION_STEP, "conclusion": value}]}
                     for value in conclusions],
        }

    def test_current_run_and_proven_skip_are_ignored(self):
        self.artifacts(2)
        self.jobs(2, "skipped")
        self.artifacts(1, artifact())
        self.assertEqual(select([run(3), run(2), run(1), run(0)], AUDITED_RUN + 3,
                                fetch=self.fetch), AUDITED_RUN + 1)

    def test_skipped_collect_job_without_steps_is_safe(self):
        self.artifacts(2)
        self.artifacts(1, artifact())
        path = f"actions/runs/{AUDITED_RUN + 2}/jobs?filter=all&per_page=100"
        for steps in (None, []):
            with self.subTest(steps=steps):
                self.responses[path] = {"total_count": 1, "jobs": [
                    dict(name="collect", status="completed", conclusion="skipped", steps=steps)
                ]}
                self.assertEqual(
                    select([run(2, conclusion="skipped"), run(1)], AUDITED_RUN + 3,
                           fetch=self.fetch),
                    AUDITED_RUN + 1,
                )

    def test_missing_steps_are_unsafe_without_exact_job_skip_evidence(self):
        self.artifacts(2)
        self.artifacts(1, artifact())
        path = f"actions/runs/{AUDITED_RUN + 2}/jobs?filter=all&per_page=100"
        job = dict(name="collect", status="completed", conclusion="skipped", steps=[])
        for conclusion, jobs, total in (
            ("failure", [job], 1),
            ("skipped", [job | dict(name="unexpected")], 1),
            ("skipped", [job | dict(status="in_progress")], 1),
            ("skipped", [job | dict(conclusion="failure")], 1),
            ("skipped", [job], 2),
            ("skipped", [job, dict(steps=[dict(name=COLLECTION_STEP, conclusion="skipped")])], 2),
        ):
            with self.subTest(conclusion=conclusion, jobs=jobs, total=total):
                self.responses[path] = dict(total_count=total, jobs=jobs)
                with self.assertRaisesRegex(ValueError, "durum paketi eksik"):
                    select([run(2, conclusion=conclusion), run(1)], AUDITED_RUN + 3,
                           fetch=self.fetch)

    def test_missing_artifact_after_started_attempt_blocks_rollback(self):
        self.artifacts(2)
        self.jobs(2, "success", "skipped")
        with self.assertRaisesRegex(ValueError, "durum paketi eksik"):
            select([run(2), run(0)], AUDITED_RUN + 3, fetch=self.fetch)

    def test_only_reviewed_exact_jobless_failure_can_be_skipped(self):
        run_id, head_sha, attempt = REVIEWED_STARTUP_FAILURE
        offset = run_id - AUDITED_RUN
        failed = run(offset, conclusion="failure") | dict(head_sha=head_sha, run_attempt=attempt)
        self.artifacts(offset)
        self.jobs(offset)
        self.artifacts(1, artifact())
        self.assertEqual(select([failed, run(1)], run_id + 1, fetch=self.fetch), AUDITED_RUN + 1)
        for changes in (dict(run_attempt=2), dict(head_sha="unknown")):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "durum paketi eksik"):
                select([failed | changes, run(1)], run_id + 1, fetch=self.fetch)
        self.artifacts(offset + 1)
        self.jobs(offset + 1)
        with self.assertRaisesRegex(ValueError, "durum paketi eksik"):
            select([failed | dict(id=run_id + 1), run(1)], run_id + 2, fetch=self.fetch)
        self.jobs(offset, "failure")
        with self.assertRaisesRegex(ValueError, "durum paketi eksik"):
            select([failed, run(1)], run_id + 1, fetch=self.fetch)

    def test_recovery_artifact_blocks_even_when_collection_was_skipped(self):
        self.artifacts(2, artifact(name="valuation-source-recovery"))
        self.jobs(2, "skipped")
        with self.assertRaisesRegex(ValueError, "durum paketi eksik"):
            select([run(2), run(0)], AUDITED_RUN + 3, fetch=self.fetch)

    def test_expired_duplicate_and_failed_artifacts_block_rollback(self):
        for items, conclusion in [
            ([artifact(expired=True)], "success"),
            ([artifact(), artifact()], "success"),
            ([artifact()], "failure"),
        ]:
            with self.subTest(items=items, conclusion=conclusion):
                self.artifacts(2, *items)
                with self.assertRaisesRegex(ValueError, "inceleme gerektiriyor"):
                    select([run(2, conclusion=conclusion), run(0)], AUDITED_RUN + 3,
                           fetch=self.fetch)

    def test_manual_request_can_only_confirm_latest_state(self):
        self.artifacts(1, artifact())
        with self.assertRaisesRegex(ValueError, "son doğrulanabilir çalışma"):
            select([run(1), run(0)], AUDITED_RUN + 2, str(AUDITED_RUN), fetch=self.fetch)
        self.assertEqual(select([run(1)], AUDITED_RUN + 2, str(AUDITED_RUN + 1),
                                fetch=self.fetch), AUDITED_RUN + 1)

    def test_active_run_and_missing_reviewed_baseline_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "bekliyor veya çalışıyor"):
            select([run(1, status="in_progress")], AUDITED_RUN + 2, fetch=self.fetch)
        self.artifacts(0)
        with self.assertRaisesRegex(ValueError, "durum paketi eksik"):
            select([run(0), run(-1)], AUDITED_RUN + 2, fetch=self.fetch)
        with self.assertRaisesRegex(ValueError, "boş durum açılmadı"):
            select([run(-1)], AUDITED_RUN + 2, fetch=self.fetch)

    def test_paginated_run_search_reaches_older_artifact(self):
        for offset in range(1, 101):
            self.artifacts(offset)
            self.jobs(offset, "skipped")
        self.artifacts(0, artifact())
        endpoint = "actions/workflows/valuation-live.yml/runs?branch=main&per_page=100&page="
        self.responses[endpoint + "1"] = {"workflow_runs": [run(i) for i in range(100, 0, -1)]}
        self.responses[endpoint + "2"] = {"workflow_runs": [run(0)]}
        self.assertEqual(select(main_runs(self.fetch), AUDITED_RUN + 101, fetch=self.fetch),
                         AUDITED_RUN)

    def test_rerun_rejected_before_api_lookup(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
            with self.assertRaisesRegex(ValueError, "yeniden denenemez"):
                runpy.run_path("scripts/select_valuation_resume.py", run_name="__main__")
