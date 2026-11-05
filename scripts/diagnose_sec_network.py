"""SEC bağlantı sorununun DNS, TCP ve TLS aşamalarını ayrı kaydet.

Bu araç HTTP/finansal veri toplamaz, kimlik bilgisi kullanmaz ve
yalnızca sabit, güvenli kaynak alan adlarını sınar.
"""
import json
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path
from argparse import ArgumentParser

HOSTS = ("data.sec.gov", "www.sec.gov", "github.com")


def diagnose_host(host, *, resolver=socket.getaddrinfo,
                  connect=socket.create_connection,
                  tls_context_factory=ssl.create_default_context):
    result = {"host": host, "dns": "unavailable", "tcp": "not_attempted",
              "tls": "not_attempted", "error_type": None}
    try:
        addresses = resolver(host, 443, type=socket.SOCK_STREAM)
        result["resolved_addresses"] = len({row[4][0] for row in addresses})
        if not addresses:
            result["error_type"] = "empty_dns_answer"
            return result
        result["dns"] = "ok"
    except (OSError, ValueError) as exc:
        result["error_type"] = type(exc).__name__
        return result
    try:
        with connect((host, 443), timeout=4) as raw:
            result["tcp"] = "ok"
            with tls_context_factory().wrap_socket(raw, server_hostname=host) as secure:
                result["tls"] = "ok"
                result["tls_version"] = secure.version()
    except (OSError, ssl.SSLError, ValueError) as exc:
        result["error_type"] = type(exc).__name__
    return result


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = {
        "kind": "sec_network_stages_diagnostic",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hosts": [diagnose_host(host) for host in HOSTS],
        "financial_data_validated": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
