import codecs
import email.utils
import http.client
import random
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
_MAX_BYTES = 20 * 1024 * 1024
_CHUNK = 64 * 1024


def _retry_after(headers) -> float | None:
    """Parse Retry-After header (seconds or HTTP-date)."""
    value = headers.get("Retry-After") if headers else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def _decompress(data: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").lower().strip()
    if encoding in ("", "identity"):
        return data
    if encoding in ("gzip", "x-gzip"):
        wbits_options = [16 + zlib.MAX_WBITS]
    elif encoding == "deflate":
        wbits_options = [zlib.MAX_WBITS, -zlib.MAX_WBITS]
    else:
        return data
    last_exc = None
    for wbits in wbits_options:
        try:
            d = zlib.decompressobj(wbits)
            out = d.decompress(data, _MAX_BYTES + 1)
            if len(out) > _MAX_BYTES:
                raise ValueError("decompressed response too large")
            return out
        except zlib.error as exc:
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def _decode(data: bytes, headers) -> str:
    charset = headers.get_content_charset() or "utf-8"
    try:
        codecs.lookup(charset)
    except LookupError:
        charset = "utf-8"
    if charset.lower().replace("_", "-") == "utf-8":
        charset = "utf-8-sig"
    return data.decode(charset, errors="replace")


def _fetch_once(url: str, timeout: float, total_timeout: float) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "curl/8.0",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    deadline = time.monotonic() + total_timeout
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        buf = bytearray()
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"total timeout {total_timeout}s exceeded")
            chunk = resp.read(_CHUNK)
            if not chunk:
                break
            buf += chunk
            if len(buf) > _MAX_BYTES:
                raise ValueError("response too large")
        data = _decompress(bytes(buf), resp.headers.get("Content-Encoding", ""))
        return _decode(data, resp.headers)


def curl_get(
        url: str,
        *,
        retries: int = 3,
        timeout: float = 15,
        total_timeout: float = 60,
        backoff: float = 1.0,
) -> str | None:
    """Fetch URL content using urllib. Returns text or None on error.

    Retries transient failures (timeouts, connection errors, 408/425/429/5xx)
    with exponential backoff + jitter, honoring Retry-After.
    """
    if urllib.parse.urlsplit(url).scheme.lower() not in ("http", "https"):
        print(f"  fetch failed for {url}: unsupported URL scheme", file=sys.stderr)
        return None

    attempts = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        delay = None
        try:
            return _fetch_once(url, timeout, total_timeout)

        except urllib.error.HTTPError as exc:
            retriable = exc.code in _RETRY_STATUS
            err: Exception = exc
            delay = _retry_after(exc.headers) if retriable else None
        except urllib.error.URLError as exc:
            err = exc
            retriable = not isinstance(exc.reason, ssl.SSLCertVerificationError)
        except (TimeoutError, socket.timeout, http.client.HTTPException,
                ConnectionError) as exc:
            err, retriable = exc, True  # IncompleteRead, RemoteDisconnected, ...
        except ssl.SSLCertVerificationError as exc:
            err, retriable = exc, False
        except (OSError, ValueError, zlib.error) as exc:
            err = exc
            retriable = isinstance(exc, OSError)

        if not retriable or attempt == attempts:
            print(f"  fetch failed for {url}: {err}", file=sys.stderr)
            return None

        if delay is None:
            delay = backoff * (2 ** (attempt - 1)) * random.uniform(0.5, 1.5)
        delay = min(delay, 30.0)
        print(f"  fetch retry {attempt}/{attempts - 1} for {url} "
              f"in {delay:.1f}s: {err}", file=sys.stderr)
        time.sleep(delay)

    return None
