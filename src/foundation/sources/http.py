from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

import requests


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    url: str
    sha256: str
    bytes: int
    content_type: str | None


def download_file(
    url: str,
    destination: Path,
    *,
    timeout: tuple[float, float] = (15.0, 180.0),
    max_bytes: int = 500_000_000,
) -> DownloadResult:
    """Stream a file to disk with size and SHA-256 checks."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")

    digest = hashlib.sha256()
    total = 0

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; The-Foundation/0.2; "
            "+https://github.com/sumosizedginger/foundation)"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{url.rsplit('/', 1)[0]}/",
    }
    with requests.get(
        url, stream=True, timeout=timeout, headers=headers, allow_redirects=True
    ) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type")

        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise RuntimeError(
                f"Refusing download larger than configured limit: {content_length} bytes"
            )

        with temp.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError("Download exceeded configured byte limit")
                digest.update(chunk)
                fh.write(chunk)

    if total <= 0:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"Refusing empty download from {url}")

    if (
        content_type
        and "html" in content_type.lower()
        and destination.suffix.lower()
        not in {
            ".html",
            ".htm",
        }
    ):
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"Refusing HTML response for non-HTML destination from {url}")

    temp.replace(destination)
    return DownloadResult(
        path=destination,
        url=url,
        sha256=digest.hexdigest(),
        bytes=total,
        content_type=content_type,
    )


def download_file_with_hash(
    url: str,
    destination: Path,
    *,
    timeout: tuple[float, float] = (15.0, 180.0),
    max_bytes: int = 500_000_000,
) -> tuple[Path, str, str]:
    """Download file and return (path, sha256_hex, retrieved_at_iso)."""
    from datetime import datetime

    res = download_file(url, destination, timeout=timeout, max_bytes=max_bytes)
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
    return res.path, res.sha256, now_iso
