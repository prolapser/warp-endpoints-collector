"""
Fetch WARP CIDRs from upstream sources.
Falls back to hardcoded list if all sources fail.
"""
import re
import sys

from curl import curl_get
from known_endpoints import CIDRS

SOURCES = [
    # 1. CloudflareWarpSpeedTest (CIDR list in Go)
    {
        "url": "https://raw.githubusercontent.com/puzige/CloudflareWarpSpeedTest/refs/heads/master/task/warping.go",
        "pattern": r'commonIPv4CIDRs\s*=\s*\[\]string\{([^}]+)\}',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 2. warp-endpoint-tester (CIDR tuple in Python)
    {
        "url": "https://raw.githubusercontent.com/geannikakakiku99532-lang/warp-endpoint-tester/refs/heads/main/check_cf_warp_endpoint.py",
        "pattern": r'CDIRS_V4\s*=\s*\(([^)]+)\)',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 3. cf-scanner (Plain text list of CIDRs)
    {
        "url": "https://raw.githubusercontent.com/mahyartdb/cf-scanner/refs/heads/main/data/warp-pools.txt",
        "pattern": r'(.*)',
        "extractor": lambda m: re.findall(r'(\d+\.\d+\.\d+\.\d+/\d+)', m),
    },
    # 4. WarpEP (CIDR tuple with type annotation in Python)
    {
        "url": "https://raw.githubusercontent.com/arjeyproject/WarpEP/refs/heads/main/warpep/endpoints.py",
        "pattern": r'IPV4_PREFIXES[^=]*=\s*\(([^)]+)\)',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 5. warp-awg-gen (24 IPs in Go -> converted to /24 subnets)
    {
        "url": "https://raw.githubusercontent.com/Skiro1/warp-awg-gen/refs/heads/master/internal/awg/endpoint.go",
        "pattern": r'knownWarpIPs\s*=\s*\[\]string\{([^}]+)\}',
        "extractor": lambda m: [f"{ip}.0/24" for ip in re.findall(r'["\'](\d+\.\d+\.\d+)\.\d+["\']', m)],
    },
    # 6. warp-scanner (14 prefixes with trailing dot in Go -> converted to /24)
    {
        "url": "https://raw.githubusercontent.com/nyeinkokoaung404/warp-scanner/refs/heads/main/main.go",
        "pattern": r'ipv4Prefixes\s*:=\s*\[\]string\{([^}]+)\}',
        "extractor": lambda m: [f"{p}0/24" for p in re.findall(r'["\'](\d+\.\d+\.\d+\.)["\']', m)],
    },
    # 7. warpscout-tg (14 netip.MustParsePrefix in Go)
    {
        "url": "https://raw.githubusercontent.com/niklzz/warpscout-tg/refs/heads/master/pools.go",
        "pattern": r'poolsV4\s*=\s*\[\]netip\.Prefix\{([^}]+)\}',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 8. warpscout (14 netip.MustParsePrefix in Go)
    {
        "url": "https://raw.githubusercontent.com/vernette/warpscout/refs/heads/master/pools.go",
        "pattern": r'poolsV4\s*=\s*\[\]netip\.Prefix\{([^}]+)\}',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 9. Oberon-Core (33 IP:Port endpoints in Go -> converted to /24)
    {
        "url": "https://raw.githubusercontent.com/rezakhosh78/Oberon-Core/refs/heads/main/scan.go",
        "pattern": r'fast\s*:=\s*\[\]string\{([^}]+)\}',
        "extractor": lambda m: [f"{ip}.0/24" for ip in re.findall(r'["\'](\d+\.\d+\.\d+)\.\d+:\d+["\']', m)],
    },
    # 10. RR-WARP-Scanner (14 netip.MustParsePrefix in Go)
    {
        "url": "https://raw.githubusercontent.com/dedikar/RR-WARP-Scanner/refs/heads/main/engine/pools.go",
        "pattern": r'poolsV4\s*=\s*\[\]netip\.Prefix\{([^}]+)\}',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 11. Warp-Endpoint-Scanner: warpip.py (9 CIDRs, including commented-out lines)
    {
        "url": "https://raw.githubusercontent.com/DarknessShade/Warp-Endpoint-Scanner/refs/heads/main/warpip.py",
        "pattern": r'warp_cidr\s*=\s*\[([^\]]+)\]',
        "extractor": lambda m: re.findall(r'["\'](\d+\.\d+\.\d+\.\d+/\d+)["\']', m),
    },
    # 12. Warp-Endpoint-Scanner: WES.py (14 prefixes in Python list -> converted to /24)
    {
        "url": "https://raw.githubusercontent.com/DarknessShade/Warp-Endpoint-Scanner/refs/heads/main/WES.py",
        "pattern": r'IPV4_PREFIXES\s*=\s*\[([^\]]+)\]',
        "extractor": lambda m: [f"{p}0/24" for p in re.findall(r'["\'](\d+\.\d+\.\d+\.)["\']', m)],
    },
]


def fetch_cidrs_from_source(source: dict) -> list[str] | None:
    """Try to extract CIDRs from a single source definition."""
    print(f"  Trying: {source['url']}")
    text = curl_get(source["url"])
    if text is None:
        return None

    match = re.search(source["pattern"], text, re.DOTALL)
    if not match:
        print("  Pattern not matched.", file=sys.stderr)
        return None

    cidrs = source["extractor"](match.group(1))
    if not cidrs:
        print("  No CIDRs extracted.", file=sys.stderr)
        return None

    return cidrs


def fetch_cidrs() -> list[str]:
    """
    Try each upstream source in order.
    Merge results from all that succeed; fall back to hardcoded list
    if none succeed or result is empty.
    """
    merged: list[str] = []

    for source in SOURCES:
        cidrs = fetch_cidrs_from_source(source)
        if cidrs:
            unique_source_cidrs = list(dict.fromkeys(cidrs))
            print(f"  Found {len(cidrs)} entries ({len(unique_source_cidrs)} unique CIDRs) from source.")
            for cidr in unique_source_cidrs:
                if cidr not in merged:
                    merged.append(cidr)

    if merged:
        print(f"Fetched {len(merged)} unique CIDRs from upstream sources.")
        return merged

    print("All upstream sources failed. Using fallback CIDRs.", file=sys.stderr)
    return list(CIDRS)


if __name__ == "__main__":
    cidrs = fetch_cidrs()
    # Print comma-separated for shell consumption
    print(",".join(cidrs))
