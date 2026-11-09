"""Doğrulanmış üretim ZIP'inden Türkçe prototip raporunu çıkar."""

import argparse
import hashlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def export_report(archive: Path, expected_sha256: str, output: Path) -> None:
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected_sha256.lower():
            raise ValueError("Skor paketinin SHA-256 özeti uyuşmuyor")
        source.seek(0)
        with ZipFile(source) as bundle:
            report = bundle.read("output/report.html")
    with output.open("xb") as destination:
        destination.write(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", required=True, help="GitHub artifact SHA-256 özeti")
    parser.add_argument("--output", type=Path, default=Path("radar.html"))
    args = parser.parse_args()
    try:
        export_report(args.archive, args.sha256, args.output)
    except (OSError, ValueError, KeyError, BadZipFile) as exc:
        parser.exit(2, f"Rapor çıkarılamadı: {exc}\n")
    print(f"Tarayıcıda açın: {args.output.resolve()}")


if __name__ == "__main__":
    main()
