"""
Parse result.csv produced by CloudflareWarpSpeedTest and emit:
  - README.md  — Markdown table (IP | Ports), sorted by IP
  - result.json — machine-readable list of {ip, ports[]}
"""
import csv
import json
from dataclasses import dataclass, field
from ipaddress import IPv4Address
from pathlib import Path

from formatter import format_md_tables_in_text

RESULT_CSV = Path("result.csv")
README_MD = Path("README.md")
RESULT_JSON = Path("result.json")

README_TEMPLATE = """\
# warp-endpoint-checker

A list of endpoints available for connecting to the **Cloudflare WARP** service,
updated automatically every week.

> The testing tool: [peanut996/CloudflareWarpSpeedTest](https://github.com/peanut996/CloudflareWarpSpeedTest)

## Available Endpoints

{table}\
"""

TABLE_HEADER = (
    "| IP Address      | Ports                                              |\n"
    "|-----------------|----------------------------------------------------|"
)


@dataclass
class Endpoint:
    ip: str
    ports: list[int] = field(default_factory=list)

    def add_port(self, port: int) -> None:
        if port not in self.ports:
            self.ports.append(port)

    @property
    def sorted_ports(self) -> list[int]:
        return sorted(self.ports)

    @property
    def ports_str(self) -> str:
        return ", ".join(str(p) for p in self.sorted_ports)

    @property
    def markdown_row(self) -> str:
        # Left-align within fixed-width columns matching the header widths:
        # IP column: 15 chars, Ports column: 50 chars
        return f"| {self.ip:<15} | {self.ports_str:<50} |"


def load_endpoints(csv_path: Path) -> list[Endpoint]:
    endpoints: dict[str, Endpoint] = {}

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw = row.get("IP:Port", "").strip()
            if not raw:
                continue
            ip, port_str = raw.rsplit(":", 1)
            ip = ip.strip()
            port = int(port_str.strip())

            if ip not in endpoints:
                endpoints[ip] = Endpoint(ip=ip)
            endpoints[ip].add_port(port)

    return list(endpoints.values())


def sort_endpoints(endpoints: list[Endpoint]) -> list[Endpoint]:
    return sorted(endpoints, key=lambda e: IPv4Address(e.ip))


def build_table(endpoints: list[Endpoint]) -> str:
    rows = "\n".join(ep.markdown_row for ep in endpoints)
    return format_md_tables_in_text(f"{TABLE_HEADER}\n{rows}")


def write_readme(endpoints: list[Endpoint]) -> None:
    table = build_table(endpoints)
    content = README_TEMPLATE.format(table=table)
    README_MD.write_text(content, encoding="utf-8")
    print(f"Written {README_MD} ({len(endpoints)} endpoints)")


def write_json(endpoints: list[Endpoint]) -> None:
    data = [
        {"ip": ep.ip, "ports": ep.sorted_ports}
        for ep in endpoints
    ]
    RESULT_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Written {RESULT_JSON} ({len(data)} entries)")


def main() -> None:
    if not RESULT_CSV.exists():
        raise FileNotFoundError(f"{RESULT_CSV} not found. Run the speed test first.")

    endpoints = load_endpoints(RESULT_CSV)
    endpoints = sort_endpoints(endpoints)

    write_readme(endpoints)
    write_json(endpoints)


if __name__ == "__main__":
    main()
