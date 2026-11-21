"""Build a unique, verified checkpoint; never overwrite an upload source path."""
import argparse,hashlib,json,sqlite3,subprocess,tempfile,tomllib,zipfile
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--test-evidence',required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=repo)
if git('status','--porcelain'):raise SystemExit('Commit the reviewed worktree before packaging')
commit=git('rev-parse','HEAD').decode().strip();branch=git('branch','--show-current').decode().strip()
evidence=json.loads((repo/args.test_evidence).read_text())
if evidence.get('failed')!=0 or evidence.get('passed')!=evidence.get('tests'):raise SystemExit('Successful test evidence required')
version=tomllib.loads((repo/'pyproject.toml').read_text())['project']['version']
parent=repo.parent/'delivery';parent.mkdir(exist_ok=True)
output=Path(tempfile.mkdtemp(prefix='checkpoint-'+commit[:8]+'-',dir=parent))
bundle=output/'us-equity-research.bundle'
subprocess.run(['git','bundle','create',str(bundle),'--all'],cwd=repo,check=True,capture_output=True)
subprocess.run(['git','bundle','verify',str(bundle)],cwd=repo,check=True,capture_output=True)
databases=[]
for name,path in [('batch-resume-live.sqlite','data/batch-resume-live.sqlite'),('submissions.sqlite','data/cache/submissions.sqlite'),
 ('annual-documents.sqlite','data/annual-documents.sqlite'),('eight-financial.sqlite','data/eight-financial.sqlite'),
 ('financial-responses.sqlite','data/financial-responses.sqlite'),('archived-financial.sqlite','data/archived-financial.sqlite')]:
 source=repo/path
 if not source.exists():continue
 a=sqlite3.connect(source);b=sqlite3.connect(output/name)
 try:
  a.backup(b)
  if b.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('database integrity failure')
 finally:b.close();a.close()
 databases.append(name)
text=f'''US Equity Research v{version} checkpoint
Commit: {commit}
Branch: {branch}
Reported local tests: {evidence['passed']}/{evidence['tests']} (see {args.test_evidence}).
Remote push/PR/Actions not implied; consult docs/DEVELOPMENT_STATUS.md.
Read docs/DEVELOPMENT_STATUS.md and docs/PROJECT_BRIEF.md before resuming.
Partial data/model/scope validation is not full-system acceptance.

Restore history:
  git clone -b {branch} us-equity-research.bundle restored-project
  cd restored-project
  PYTHONPATH=src python3 -m unittest discover -s tests -v
Source-only copy is under us-equity-research/.
Public operational DB snapshots are under evidence-checkpoints/ when available.
Restore their appropriate data/ or data/cache/ paths as documented in status.
Original source timestamps and TTLs remain in force; policy changes can invalidate
old financial outcomes. No credential or auth header belongs in this checkpoint.
Do not force-push unrelated history onto initialized main; branch from target main,
copy reviewed sources excluding .git, test, open a PR and merge after verification.
'''
(output/'CHECKPOINT.txt').write_text(text)
archive=output/'us-equity-research-foundation.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for relative in git('ls-files','-z').decode().split('\0'):
  if relative:z.write(repo/relative,'us-equity-research/'+relative)
 z.write(bundle,bundle.name);z.write(output/'CHECKPOINT.txt','CHECKPOINT.txt')
 for name in databases:z.write(output/name,'evidence-checkpoints/'+name)
with zipfile.ZipFile(archive) as z:
 bad=z.testzip()
 if bad:raise ValueError('archive CRC failure: '+bad)
 if commit not in z.read('CHECKPOINT.txt').decode():raise ValueError('checkpoint identity mismatch')
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
manifest=dict(archive=str(archive),sha256=sha,size_bytes=archive.stat().st_size,commit=commit,branch=branch,
 test_evidence=args.test_evidence,tests=evidence['tests'],database_snapshots=databases)
(output/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
