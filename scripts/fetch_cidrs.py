"""
Fetch WARP CIDRs from upstream sources.
Falls back to hardcoded list if all sources fail.
"""
import re
import subprocess
import sys

FALLBACK_CIDRS = [
    "162.159.192.0/24",
    "162.159.193.0/24",
    "162.159.195.0/24",
    "162.159.204.0/24",
    "188.114.96.0/24",
    "188.114.97.0/24",
    "188.114.98.0/24",
    "188.114.99.0/24",
    "8.34.146.0/24",
    "8.47.69.0/24",
]

SOURCES = [
    {
        "url": (
            "https://raw.githubusercontent.com/"
            "peanut996/CloudflareWarpSpeedTest/"
            "refs/heads/master/task/warping.go"
        ),
        # matches string literals inside commonIPv4CIDRs = []string{ ... }
        "pattern": r'commonIPv4CIDRs\s*=\s*\[\]string\{([^}]+)\}',
        "extractor": lambda m: re.findall(r'"(\d+\.\d+\.\d+\.\d+/\d+)"', m),
    },
    {
        "url": (
            "https://raw.githubusercontent.com/"
            "geannikakakiku99532-lang/warp-endpoint-tester/"
            "refs/heads/main/check_cf_warp_endpoint.py"
        ),
        # matches string literals inside CDIRS_V4 = ( ... )
        "pattern": r'CDIRS_V4\s*=\s*\(([^)]+)\)',
        "extractor": lambda m: re.findall(r'"(\d+\.\d+\.\d+\.\d+/\d+)"', m),
    },
]


def curl_get(url: str) -> str | None:
    """Fetch URL content via curl subprocess. Returns text or None on error."""
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "15", url],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        print(f"  curl failed for {url}: {exc}", file=sys.stderr)
        return None


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
    merged: list[str] = FALLBACK_CIDRS

    for source in SOURCES:
        cidrs = fetch_cidrs_from_source(source)
        if cidrs:
            print(f"  Found {len(cidrs)} CIDRs from source.")
            for cidr in cidrs:
                if cidr not in merged:
                    merged.append(cidr)

    if merged:
        print(f"Fetched {len(merged)} unique CIDRs from upstream sources.")
        return merged

    print("All upstream sources failed. Using fallback CIDRs.", file=sys.stderr)
    return FALLBACK_CIDRS


if __name__ == "__main__":
    cidrs = fetch_cidrs()
    # Print comma-separated for shell consumption
    print(",".join(cidrs))
