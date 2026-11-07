"""Verified run-6 lineage. No fallback to an older/empty state on errors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT_RUN = 42223465006
# Run 42277691544 (sequence 6) was audited before authorizing one more slice.
# See docs/evidence/live-run13-audit.json. Review again after sequence 7.
MAX_REVIEWED_SEQUENCE = 7
REPO = 'fatalvayn-dot/us-equity-research'
MANIFEST = 'checkpoint-manifest.json'
REQUIRED = {'submissions.sqlite', 'documents.sqlite', 'financial.sqlite',
            'responses.sqlite', 'run-lock.sqlite'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Sembolik bağlantı içeren durum reddedildi')
        if p.is_file() and p.name != MANIFEST:
            result[p.relative_to(root).as_posix()] = digest(p)
    if not REQUIRED.issubset(result):
        raise ValueError('Zorunlu durum veritabanı eksik')
    return result


def inspect_databases(root, now=None, *, allow_active=False):
    now = now or datetime.now(timezone.utc)
    counts = {}
    for p in root.rglob('*.sqlite'):
        with sqlite3.connect(f'file:{p.resolve()}?mode=ro', uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('SQLite bütünlük hatası')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'batch_lease_v1' in tables:
                for stamp, in db.execute('SELECT expires FROM batch_lease_v1'):
                    if datetime.fromisoformat(stamp) > now and not allow_active:
                        raise ValueError('Etkin kira var; toplayıcı başlatılmadı')
            if 'batch_fields_v1' in tables:
                for payload, checksum in db.execute('SELECT payload,checksum FROM batch_fields_v1'):
                    if hashlib.sha256(payload.encode()).hexdigest() != checksum:
                        raise ValueError('Alan kaydı özeti uyuşmuyor')
                    json.loads(payload)
            if 'response_bodies_v1' in tables:
                for sha, body in db.execute('SELECT sha256,body FROM response_bodies_v1'):
                    if hashlib.sha256(body).hexdigest() != sha:
                        raise ValueError('Ham kaynak özeti uyuşmuyor')
                if db.execute('SELECT COUNT(*) FROM response_observations_v1 o LEFT JOIN response_bodies_v1 b USING(sha256) WHERE b.sha256 IS NULL').fetchone()[0]:
                    raise ValueError('Ham kaynak kaydı eksik')
            counts[p.name] = {t: db.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0] for t in sorted(tables)}
    return counts


def verify(root, run_id, baseline):
    path = root / MANIFEST
    saved = json.loads(path.read_text()) if path.exists() else baseline
    if saved['root_run_id'] != ROOT_RUN or saved['run_id'] != run_id:
        raise ValueError('Kontrol noktası çalışma kimliği uyuşmuyor')
    if inventory(root) != saved['files']:
        raise ValueError('Kontrol noktası dosyaları eksik veya değiştirilmiş')
    return saved, inspect_databases(root)


def collection_never_started(jobs):
    steps = [s for job in jobs for s in job.get('steps', [])
             if s['name'] == 'Devam ettirilebilir finansal veri toplamasını çalıştır']
    return bool(steps) and all(s.get('conclusion') == 'skipped' for s in steps)


def select(runs, artifacts, current_run, requested='', safe_to_skip=None):
    for run in sorted(runs, key=lambda r: r['id'], reverse=True):
        if run['id'] == current_run or run['id'] < ROOT_RUN:
            continue
        if run['head_branch'] != 'main' or run['event'] not in ('workflow_dispatch', 'schedule', 'push'):
            continue
        if run['status'] != 'completed':
            raise ValueError('Başka canlı toplayıcı bekliyor veya çalışıyor')
        items = artifacts(run['id'])
        if any(a['name'] == 'live-acceptance-recovery' for a in items):
            raise ValueError('Son çalışmanın kurtarma paketi incelenmeli; eski duruma dönülmedi')
        states = [a for a in items if a['name'] == 'live-acceptance-state']
        if not states:
            if run['id'] != ROOT_RUN and not (safe_to_skip and safe_to_skip(run['id'])):
                raise ValueError('Durum arşivi yok; veri toplama başlamadığı doğrulanmadan eski duruma dönülmedi')
            continue
        if len(states) != 1 or states[0]['expired']:
            raise ValueError('Son durum arşivi kullanılamıyor; eski duruma dönülmedi')
        if requested and str(run['id']) != requested:
            raise ValueError('Eski çalışma seçimi reddedildi; son durum kullanılmalı')
        return run['id']
    raise ValueError('Run #6 veya devam durumu bulunamadı')


def api(path):
    request = Request('https://api.github.com/repos/' + REPO + '/' + path,
                      headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                               'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def safe_run_skip(run_id):
    result = api(f'actions/runs/{run_id}/jobs?filter=all&per_page=100')
    # A concurrency-cancelled queued run can have no jobs at all.
    return (result['total_count'] == len(result['jobs'])
            and (not result['jobs'] or collection_never_started(result['jobs'])))


def require_first_attempt():
    # GitHub reruns reuse the run ID. select() excludes that ID, so a retry
    # could restore its older parent instead of the first attempt's new data.
    # Require a fresh workflow run; leave all existing artifacts untouched.
    if int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')) != 1:
        raise ValueError(
            'Aynı canlı çalışma yeniden denenemez; önceki denemenin verisi '
            'korundu. Yeni workflow_dispatch çalışması başlatın; son güvenli '
            'durum otomatik seçilecektir.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['select', 'verify', 'seal'])
    p.add_argument('--state-dir', default='data/live-acceptance')
    p.add_argument('--run-id', type=int)
    p.add_argument('--requested', default='')
    p.add_argument('--baseline', default='docs/evidence/live-run6-checkpoint.json')
    args = p.parse_args()
    root = Path(args.state_dir)
    if args.action == 'select':
        require_first_attempt()
        runs = []
        for page in range(1, 11):
            rows = api(f'actions/workflows/live-acceptance.yml/runs?branch=main&per_page=100&page={page}')['workflow_runs']
            runs.extend(rows)
            if not rows or min(r['id'] for r in rows) <= ROOT_RUN:
                break
        else:
            raise ValueError('Çalışma araması sınırı aşıldı')
        run_id = select(runs, lambda rid: api(f'actions/runs/{rid}/artifacts?per_page=100')['artifacts'],
                        int(os.environ['GITHUB_RUN_ID']), args.requested,
                        safe_to_skip=safe_run_skip)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'run_id={run_id}\n')
        print(json.dumps({'resume_run_id': run_id}))
    elif args.action == 'verify':
        saved, counts = verify(root, args.run_id, json.loads(Path(args.baseline).read_text()))
        # Preserve the exact parent reference before changing any collection file.
        receipt = dict(parent_run_id=args.run_id, root_run_id=ROOT_RUN, sequence=saved['sequence'])
        (root.parent / 'resume-receipt.json').write_text(json.dumps(receipt))
        with open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a') as f:
            f.write(f"collect={'true' if saved['sequence'] < MAX_REVIEWED_SEQUENCE else 'false'}\n")
        if saved['sequence'] >= MAX_REVIEWED_SEQUENCE:
            print('İncelenen devam bütçesi tamamlandı; yeni veri çağrısından önce teknik inceleme gerekiyor.')
            summary = os.environ.get('GITHUB_STEP_SUMMARY')
            if summary:
                with open(summary, 'a') as f:
                    f.write('\n## Veri toplama teknik inceleme bekliyor\n\n'
                            'Bu koşu yeni finansal veri toplamaz. Başarılı bütünlük '
                            'kontrolü, yeni veri ilerlemesi veya MVP kabulü değildir.\n\n'
                            f"Doğrulanan durum run ID: {args.run_id}; "
                            f"devam sırası: {saved['sequence']}; "
                            f"incelenmiş sınır: {MAX_REVIEWED_SEQUENCE}.\n\n"
                            'Son durum ve kaynak kanıtlarını inceleyin; bütçeyi '
                            'körlemesine artırmayın.\n')
        print(json.dumps({'verified_run_id': args.run_id, 'tables': counts}))
    else:
        receipt = json.loads((root.parent / 'resume-receipt.json').read_text())
        inspect_databases(root, allow_active=True)
        manifest = dict(root_run_id=ROOT_RUN, parent_run_id=receipt['parent_run_id'],
                        run_id=args.run_id, sequence=receipt['sequence'] + 1, files=inventory(root))
        temporary = root / (MANIFEST + '.tmp')
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(root / MANIFEST)
        print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
