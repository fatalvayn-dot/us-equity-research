"""Verify a downloaded valuation checkpoint before the collector opens it."""
import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from equity_research.evidence_bundle import read_bundle
from scripts.live_checkpoint import inspect_databases


def verified_observations(root: Path) -> set[tuple[str, str, str]]:
    required_tables = {
        "sources.sqlite": {"response_bodies_v1", "response_observations_v1"},
        "run-lock.sqlite": {"batch_fields_v1", "batch_lease_v1"},
    }
    for name in required_tables:
        if not (root / name).is_file():
            raise ValueError(f"Değerleme durum dosyası eksik: {name}")
    counts = inspect_databases(root)
    for name, tables in required_tables.items():
        if not tables.issubset(counts.get(name, {})):
            raise ValueError(f"Değerleme SQLite şeması eksik: {name}")

    report = json.loads((root / "report.json").read_text())
    bundle = root / "source-bundle"
    manifest = json.loads((bundle / "manifest.json").read_text())
    if report["source_bundle"] != manifest:
        raise ValueError("Değerleme raporu ile kaynak manifesti uyuşmuyor")

    database = (root / "sources.sqlite").resolve().as_uri()
    with closing(sqlite3.connect(f"{database}?mode=ro", uri=True)) as db:
        observations = set(db.execute(
            "SELECT url, sha256, retrieved_at FROM response_observations_v1"
        ))
    verified = set()
    for response in read_bundle(bundle):
        key = (response.url, response.sha256, response.retrieved_at.isoformat())
        if key not in observations:
            raise ValueError("Kaynak paketi gözlemi SQLite kaydıyla uyuşmuyor")
        observations.remove(key)
        verified.add(key)
    if observations:
        raise ValueError("SQLite kaynak gözlemi pakette eksik")
    return verified


def verify(root: Path, *, previous_state: Path | None = None,
           write_observations: Path | None = None,
           require_observations: Path | None = None) -> int:
    current = verified_observations(root)
    previous = verified_observations(previous_state) if previous_state is not None else set()
    if require_observations is not None:
        rows = json.loads(require_observations.read_text())
        if not isinstance(rows, list) or any(
                not isinstance(row, list) or len(row) != 3
                or not all(isinstance(value, str) for value in row) for row in rows):
            raise ValueError("Önceki değerleme gözlem kaydı geçersiz")
        previous.update(map(tuple, rows))
    missing = previous - current
    if missing:
        raise ValueError(f"Önceki değerleme durumundan {len(missing)} kaynak gözlemi kayıp")
    if write_observations is not None:
        write_observations.write_text(json.dumps(sorted(current)) + "\n")
    return len(current)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_dir", type=Path)
    parser.add_argument("--previous-state", type=Path,
                        help="Önceki doğrulanmış paketteki gözlemlerin tamamını karşılaştır")
    receipt = parser.add_mutually_exclusive_group()
    receipt.add_argument("--write-observations", type=Path)
    receipt.add_argument("--require-observations", type=Path)
    args = parser.parse_args()
    count = verify(args.state_dir, previous_state=args.previous_state,
                   write_observations=args.write_observations,
                   require_observations=args.require_observations)
    print(f"Doğrulanan değerleme kaynak gözlemi: {count}")
