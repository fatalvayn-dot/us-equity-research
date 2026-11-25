"""Recover score handoff artifacts from one pinned fresh100 evidence artifact."""
import argparse
import base64
import gzip
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


PUBLIC_HOSTS = frozenset({
    "www.sec.gov", "data.sec.gov", "query1.finance.yahoo.com",
    "api.nasdaq.com", "www.nasdaq.com", "www.nasdaqtrader.com",
    "ftp.nasdaqtrader.com",
})
COMPANYFACTS = re.compile(
    r"^https://data\.sec\.gov/api/xbrl/companyfacts/CIK([0-9]{10})\.json$"
)


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _public_url(url: str) -> None:
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in PUBLIC_HOSTS
            or parts.port not in (None, 443) or parts.username or parts.password
            or parts.fragment or any(ord(char) < 32 for char in url)):
        raise ValueError("yalnız açık ve izinli kaynak URL'si kabul edilir")
    for key, _ in parse_qsl(parts.query, keep_blank_values=True):
        normalized = re.sub("[^a-z0-9]", "", key.lower())
        if (normalized == "key" or any(word in normalized for word in
                ("token", "apikey", "password", "secret", "authorization", "crumb"))):
            raise ValueError("kimlik bilgisi taşıyan URL arşivlenemez")


def _bundle_rows(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_text())
    if (manifest.get("schema_version") != 1
            or manifest.get("format") != "gzip-jsonl-public-response-observations-v1"
            or manifest.get("headers_stored") is True
            or manifest.get("credentials_stored") is True):
        raise ValueError("desteklenmeyen kaynak paketi")
    with tempfile.TemporaryFile() as combined:
        compressed = hashlib.sha256()
        for index, part in enumerate(manifest.get("parts", [])):
            if part.get("file") != f"sources.jsonl.gz.part{index:04d}":
                raise ValueError("kaynak parça sırası geçersiz")
            body = (directory / part["file"]).read_bytes()
            if len(body) != part.get("bytes") or digest(body) != part.get("sha256"):
                raise ValueError("kaynak parça bütünlüğü bozuk")
            combined.write(body)
            compressed.update(body)
        if compressed.hexdigest() != manifest.get("compressed_sha256"):
            raise ValueError("sıkıştırılmış kaynak paketi SHA değeri uyuşmuyor")
        combined.seek(0)
        count = 0
        with gzip.GzipFile(fileobj=combined, mode="rb") as raw:
            for line in raw:
                row = json.loads(line)
                _public_url(row["url"])
                body = base64.b64decode(row["body_base64"], validate=True)
                stamp = datetime.fromisoformat(row["retrieved_at"])
                if stamp.utcoffset() is None or digest(body) != row["sha256"]:
                    raise ValueError("özgün kaynak gövdesi bütünlüğü bozuk")
                count += 1
                yield row, body
        if count != manifest.get("observations"):
            raise ValueError("kaynak gözlem sayısı uyuşmuyor")


def _exported(evidence: Path, logical_name: str) -> bytes:
    manifest = json.loads((evidence / "reports-manifest.json").read_text())
    matches = [row for row in manifest.get("files", [])
               if row.get("logical_name") == logical_name]
    if len(matches) != 1:
        raise ValueError(f"{logical_name} kanıt manifestinde tekil değil")
    row = matches[0]
    stored = row.get("file")
    if not isinstance(stored, str) or Path(stored).name != stored:
        raise ValueError("geçersiz kanıt dosya yolu")
    payload = (evidence / stored).read_bytes()
    if digest(payload) != row.get("stored_sha256"):
        raise ValueError("saklanan rapor SHA değeri uyuşmuyor")
    if row.get("encoding") == "gzip":
        body = gzip.decompress(payload)
    elif row.get("encoding") == "identity":
        body = payload
    else:
        raise ValueError("desteklenmeyen rapor kodlaması")
    if len(body) != row.get("raw_bytes") or digest(body) != row.get("raw_sha256"):
        raise ValueError("özgün rapor SHA değeri uyuşmuyor")
    return body


def _identities(rows, label):
    result = []
    for row in rows:
        cik, symbol = row.get("issuer_id"), row.get("symbol")
        if (not isinstance(cik, str) or len(cik) != 10 or not cik.isdecimal()
                or not isinstance(symbol, str) or not symbol.strip()):
            raise ValueError(f"{label} geçersiz şirket kimliği içeriyor")
        result.append((cik, symbol))
    if len(result) != 100 or len(set(result)) != 100:
        raise ValueError(f"{label} tam 100 tekil şirket içermelidir")
    return set(result)


def recover(*, candidates: Path, recovery_manifest: Path, evidence_root: Path,
            output: Path, publish_run_id: int) -> dict:
    if type(publish_run_id) is not int or publish_run_id <= 0:
        raise ValueError("yayın run ID pozitif olmalıdır")
    pin = json.loads(recovery_manifest.read_text())
    if (pin.get("schema_version") != 1
            or pin.get("purpose") != "fresh100_failed_handoff_artifact_recovery"
            or pin.get("network_requests_allowed") is not False
            or pin.get("investment_approved") is not False):
        raise ValueError("geçersiz recovery sabitlemesi")
    candidate_body = candidates.read_bytes()
    if digest(candidate_body) != pin.get("candidate_sha256"):
        raise ValueError("aday dosyası SHA değeri sabitlemeyle uyuşmuyor")
    candidate_document = json.loads(candidate_body)
    candidate_rows = (candidate_document.get("companies")
                      if isinstance(candidate_document, dict) else candidate_document)
    if not isinstance(candidate_rows, list):
        raise ValueError("aday dosyası şirket listesi içermiyor")
    expected = _identities(candidate_rows, "Aday dosyası")

    financial_evidence = evidence_root / "financial-evidence"
    financial_sources = evidence_root / "financial-sources"
    valuation = evidence_root / "valuation"
    batch_body = _exported(financial_evidence, "batch.json")
    metadata_body = _exported(financial_evidence, "metadata.json")
    batch = json.loads(batch_body)
    metadata = json.loads(metadata_body)
    valuation_body = (valuation / "report.json").read_bytes()
    valuation_report = json.loads(valuation_body)
    if (_identities(batch.get("companies", []), "Finansal paket") != expected
            or _identities(metadata.get("companies", []), "Metadata paketi") != expected
            or _identities(valuation_report.get("companies", []), "Değerleme paketi") != expected):
        raise ValueError("recovery paketlerinin şirket kohortu uyuşmuyor")

    finance_manifest = json.loads((financial_sources / "manifest.json").read_text())
    valuation_manifest = json.loads((valuation / "source-bundle/manifest.json").read_text())
    if (finance_manifest.get("observations") != pin.get("financial_observations")
            or finance_manifest.get("compressed_sha256") != pin.get("financial_bundle_sha256")
            or valuation_manifest.get("observations") != pin.get("valuation_observations")
            or valuation_manifest.get("compressed_sha256") != pin.get("valuation_bundle_sha256")):
        raise ValueError("kaynak paketi sabitlemesi uyuşmuyor")

    facts = {}
    invalid_companyfacts = 0
    for row, body in _bundle_rows(financial_sources):
        matched = COMPANYFACTS.fullmatch(row["url"])
        if not matched or matched.group(1) not in {cik for cik, _ in expected}:
            continue
        cik = matched.group(1)
        if cik in facts:
            raise ValueError("yinelenen CompanyFacts gözlemi")
        payload = json.loads(body)
        if (payload.get("cik") != int(cik) or not isinstance(payload.get("facts"), dict)
                or not isinstance(payload.get("entityName"), str)):
            invalid_companyfacts += 1
            continue
        facts[cik] = (row, body)
    if len(facts) != pin.get("companyfacts_snapshots"):
        raise ValueError("CompanyFacts snapshot sayısı sabitlemeyle uyuşmuyor")
    if invalid_companyfacts != pin.get("invalid_companyfacts_observations", 0):
        raise ValueError("geçersiz CompanyFacts gözlem sayısı sabitlemeyle uyuşmuyor")
    for company in batch["companies"]:
        cik = company["issuer_id"]
        sec_hashes = {field["fact"]["raw_sha256"] for field in company.get("fields", [])
                      if field.get("fact") and field["fact"].get("source") == "SEC"}
        if sec_hashes and (cik not in facts or sec_hashes != {facts[cik][0]["sha256"]}):
            raise ValueError("seçilmiş SEC fact ile CompanyFacts SHA zinciri uyuşmuyor")
    valuation_count = sum(1 for _ in _bundle_rows(valuation / "source-bundle"))
    if valuation_count != pin.get("valuation_observations"):
        raise ValueError("değerleme kaynak gözlem sayısı uyuşmuyor")

    if output.exists():
        raise ValueError("recovery hedefi boş olmalıdır")
    finance_out = output / "financial"
    evidence_out = output / "financial-evidence/live-sources"
    valuation_out = output / "valuation"
    companyfacts_out = finance_out / "companyfacts"
    companyfacts_out.mkdir(parents=True)
    evidence_out.parent.mkdir(parents=True)
    valuation_out.mkdir(parents=True)
    (finance_out / "batch.json").write_bytes(batch_body)
    (finance_out / "metadata.json").write_bytes(metadata_body)
    for cik, (row, body) in facts.items():
        envelope = {"url": row["url"], "body": body.decode("utf-8"),
                    "retrieved_at": row["retrieved_at"], "sha256": row["sha256"]}
        (companyfacts_out / f"{cik}.json").write_text(json.dumps(envelope))
    shutil.copytree(financial_sources, evidence_out)
    (valuation_out / "report.json").write_bytes(valuation_body)
    shutil.copytree(valuation / "source-bundle", valuation_out / "source-bundle")
    (valuation_out / "financial-source-run.json").write_text(json.dumps({
        "run_id": publish_run_id,
        "source_run_id": pin["source_run_id"],
        "recovered_from_artifact_id": pin["source_artifact_id"],
    }) + "\n")
    receipt = {
        "schema_version": 1,
        "purpose": "fresh100_same_cohort_artifact_recovery",
        "source_run_id": pin["source_run_id"],
        "publish_run_id": publish_run_id,
        "source_artifact_id": pin["source_artifact_id"],
        "source_artifact_digest": pin["source_artifact_digest"],
        "companies": 100,
        "companyfacts_snapshots": len(facts),
        "invalid_companyfacts_observations": invalid_companyfacts,
        "financial_observations": finance_manifest["observations"],
        "valuation_observations": valuation_count,
        "candidate_sha256": digest(candidate_body),
        "financial_batch_sha256": digest(batch_body),
        "metadata_sha256": digest(metadata_body),
        "valuation_report_sha256": digest(valuation_body),
        "recovered_without_provider_requests": True,
        "network_requests": 0,
        "scores_generated": 0,
        "investment_approved": False,
    }
    (valuation_out / "cohort-handoff.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidates", "recovery-manifest", "evidence-root", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--publish-run-id", type=int, required=True)
    print(json.dumps(recover(**vars(parser.parse_args())), ensure_ascii=False))


if __name__ == "__main__":
    main()
