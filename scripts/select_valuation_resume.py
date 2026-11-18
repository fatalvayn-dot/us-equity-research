"""Choose the newest safe valuation checkpoint without rolling back."""
import os
from datetime import datetime

from scripts.live_checkpoint import api, require_first_attempt

WORKFLOW = "valuation-live.yml"
COLLECTION_STEP = "Güncel fiyat ve hisse sınıfı kanıtlarını kontrollü topla"
AUDITED_RUN = 42536567400
# GitHub reported an internal server error before any job existed for this
# exact attempt. See the reviewed startup failure in DEVELOPMENT_STATUS.md.
REVIEWED_STARTUP_FAILURE = (42671436322, "a4917167600ed16d04621a2b5f1484a83d788a0f", 1)
# Attempt 1 published this state successfully. Attempt 2 stopped before
# collection at the existing rerun guard and changed the run-level conclusion.
REVIEWED_PUBLISHED_RERUN = (
    44237805936, "ee31816b7043d87d170a8db117b5bb85af313bdc",
    14399086616, "sha256:8c4d30f07da2e88a1897ed6a1c822ffd0333d57db73cc7a4889ba0d397dd1c13",
)


def reviewed_publication_survives_rerun(run, state, fetch):
    if (run["id"], run.get("head_sha"), state.get("id"), state.get("digest")) != REVIEWED_PUBLISHED_RERUN:
        return False
    if run.get("run_attempt") != 2 or run.get("conclusion") != "failure":
        return False
    first = fetch(f"actions/runs/{run['id']}/attempts/1")
    if (first.get("id"), first.get("head_sha"), first.get("run_attempt"),
            first.get("status"), first.get("conclusion")) != (
            run["id"], run["head_sha"], 1, "completed", "success"):
        return False
    data = fetch(f"actions/runs/{run['id']}/jobs?filter=all&per_page=100")
    jobs = data["jobs"]
    if len(jobs) != data["total_count"] or len(jobs) != 2:
        return False
    by_attempt = {job.get("run_attempt"): job for job in jobs}
    if set(by_attempt) != {1, 2}:
        return False
    original, retry = by_attempt[1], by_attempt[2]
    required = {COLLECTION_STEP, "Yeni değerleme durumunu ve kaynak devamlılığını doğrula",
                "Değerleme kanıtını ve devam durumunu koru"}
    if (original.get("conclusion") != "success"
            or not required <= {step["name"] for step in original.get("steps", [])
                                if step.get("conclusion") == "success"}):
        return False
    collection = [step for step in retry.get("steps", []) if step["name"] == COLLECTION_STEP]
    if (retry.get("status") != "completed" or retry.get("conclusion") != "failure"
            or len(collection) != 1 or collection[0].get("conclusion") != "skipped"):
        return False
    return (datetime.fromisoformat(original["started_at"])
            <= datetime.fromisoformat(state["created_at"])
            <= datetime.fromisoformat(original["completed_at"])
            < datetime.fromisoformat(retry["started_at"]))


def main_runs(fetch=api):
    for page in range(1, 11):
        rows = fetch(
            f"actions/workflows/{WORKFLOW}/runs?branch=main&per_page=100&page={page}"
        )["workflow_runs"]
        yield from rows
        if len(rows) < 100:
            return
    raise ValueError("Değerleme çalışma araması sınırı aşıldı")


def collection_skipped(run, fetch):
    data = fetch(f"actions/runs/{run['id']}/jobs?filter=all&per_page=100")
    jobs = data["jobs"]
    if len(jobs) != data["total_count"]:
        return False
    if not jobs:
        return (run["conclusion"] in {"cancelled", "skipped"}
                or (run["conclusion"] == "failure"
                    and (run["id"], run.get("head_sha"), run.get("run_attempt"))
                    == REVIEWED_STARTUP_FAILURE))
    # GitHub omits all steps when the collect job condition is false.
    if len(jobs) == 1 and run["conclusion"] == "skipped":
        job = jobs[0]
        if (job.get("name") == "collect" and job.get("status") == "completed"
                and job.get("conclusion") == "skipped" and job.get("steps") in (None, [])):
            return True
    if any(not job.get("steps") for job in jobs):
        return False
    steps = [step for job in jobs for step in job["steps"]
             if step["name"] == COLLECTION_STEP]
    return bool(steps) and all(step["conclusion"] == "skipped" for step in steps)


def select(runs, current_run, requested="", *, fetch=api):
    for run in runs:
        run_id = run["id"]
        if run_id == current_run or run["head_branch"] != "main":
            continue
        if run_id < AUDITED_RUN:
            break
        if run["status"] != "completed":
            raise ValueError(f"Değerleme çalışması bekliyor veya çalışıyor ({run_id})")
        data = fetch(f"actions/runs/{run_id}/artifacts?per_page=100")
        if len(data["artifacts"]) != data["total_count"]:
            raise ValueError(f"Değerleme paket listesi eksik ({run_id})")
        states = [item for item in data["artifacts"]
                  if item["name"] == "valuation-source-state"]
        if not states:
            if run_id != AUDITED_RUN and not data["artifacts"] and collection_skipped(run, fetch):
                continue
            raise ValueError(f"Değerleme durum paketi eksik ({run_id}); eski duruma dönülmedi")
        if (len(states) != 1 or states[0]["expired"]
                or (run["conclusion"] != "success"
                    and (len(data["artifacts"]) != 1
                         or not reviewed_publication_survives_rerun(run, states[0], fetch)))):
            raise ValueError(
                f"Değerleme durum paketi inceleme gerektiriyor ({run_id}); eski duruma dönülmedi"
            )
        if requested and requested != str(run_id):
            raise ValueError(f"Değerleme için son doğrulanabilir çalışma kullanılmalı ({run_id})")
        return run_id
    raise ValueError("Denetlenmiş değerleme durumu bulunamadı; boş durum açılmadı")


if __name__ == "__main__":
    require_first_attempt()
    print(select(main_runs(), int(os.environ["GITHUB_RUN_ID"]),
                 os.environ.get("RESUME_RUN_INPUT", "")))
