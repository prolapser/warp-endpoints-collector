"""
Download the latest CloudflareWarpSpeedTest binary and run the speed test.
"""
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from fetch_cidrs import fetch_cidrs

API_URL = "https://api.github.com/repos/peanut996/CloudflareWarpSpeedTest/releases/latest"
BINARY_NAME = "CloudflareWarpSpeedTest"
PLATFORM = "linux-amd64"

# Speed-test parameters
PARALLEL_WORKERS = 500
TIMEOUT_SECONDS = 3


def curl_get(url: str) -> str | None:
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "--max-time", "30", url],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        print(f"curl failed for {url}: {exc}", file=sys.stderr)
        return None


def get_latest_tag() -> str:
    import json

    print("Fetching latest release tag...")
    text = curl_get(API_URL)
    if text is None:
        sys.exit("Failed to fetch latest release info.")

    data = json.loads(text)
    tag = data.get("tag_name")
    if not tag:
        sys.exit("tag_name not found in API response.")

    print(f"Latest tag: {tag}")
    return tag


def download_and_extract_binary(tag: str, dest_dir: Path) -> Path:
    filename = f"{BINARY_NAME}-{tag}-{PLATFORM}.tar.gz"
    url = (
        f"https://github.com/peanut996/CloudflareWarpSpeedTest"
        f"/releases/download/{tag}/{filename}"
    )
    archive_path = dest_dir / filename

    print(f"Downloading {url} ...")
    subprocess.run(
        ["curl", "-fsSL", "--max-time", "120", "-o", str(archive_path), url],
        check=True,
    )

    print("Extracting archive...")
    with tarfile.open(archive_path) as tar:
        tar.extractall(path=dest_dir)

    binary = dest_dir / BINARY_NAME
    if not binary.exists():
        matches = list(dest_dir.rglob(BINARY_NAME))
        if not matches:
            sys.exit(f"Binary '{BINARY_NAME}' not found after extraction.")
        binary = matches[0]

    binary.chmod(0o755)
    print(f"Binary ready: {binary}")
    return binary


def run_speed_test(binary: Path, cidrs: list[str]) -> None:
    cidr_arg = ",".join(cidrs)
    cmd = [
        str(binary),
        "-ip", cidr_arg,
        "-all",
        "-n", str(PARALLEL_WORKERS),
        "-t", str(TIMEOUT_SECONDS),
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=Path.cwd())


def main() -> None:
    cidrs = fetch_cidrs()
    print(f"CIDRs to test: {cidrs}")

    tag = get_latest_tag()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        binary = download_and_extract_binary(tag, tmp_path)
        run_speed_test(binary, cidrs)


if __name__ == "__main__":
    main()
