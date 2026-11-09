"""Choose the newest safe valuation checkpoint without rolling back."""
import os

from scripts.live_checkpoint import api, require_first_attempt

WORKFLOW = "valuation-live.yml"
COLLECTION_STEP = "Güncel fiyat ve hisse sınıfı kanıtlarını kontrollü topla"
AUDITED_RUN = 42536567400


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
        return run["conclusion"] in {"cancelled", "skipped"}
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
            if run_id != AUDITED_RUN and collection_skipped(run, fetch):
                continue
            raise ValueError(f"Değerleme durum paketi eksik ({run_id}); eski duruma dönülmedi")
        if len(states) != 1 or states[0]["expired"] or run["conclusion"] != "success":
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
