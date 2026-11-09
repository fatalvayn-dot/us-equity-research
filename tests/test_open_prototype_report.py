import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.open_prototype_report import export_report


class OpenPrototypeReportTests(unittest.TestCase):
    def test_extracts_only_the_verified_html_and_protects_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, output = root / "score.zip", root / "radar.html"
            html = "<html lang='tr'>Araştırma raporu</html>".encode()
            with ZipFile(archive, "w") as bundle:
                bundle.writestr("output/report.html", html)
                bundle.writestr("../other.txt", "unused")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()

            with self.assertRaisesRegex(ValueError, "SHA-256"):
                export_report(archive, "0" * 64, output)
            self.assertFalse(output.exists())

            export_report(archive, digest, output)
            self.assertEqual(output.read_bytes(), html)
            self.assertEqual(set(root.iterdir()), {archive, output})
            with self.assertRaises(FileExistsError):
                export_report(archive, digest, output)
            self.assertEqual(output.read_bytes(), html)
