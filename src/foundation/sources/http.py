from __future__ import annotations

import hashlib
from dataclasses import dataclass
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

    with requests.get(url, stream=True, timeout=timeout) as response:
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

    temp.replace(destination)
    return DownloadResult(
        path=destination,
        url=url,
        sha256=digest.hexdigest(),
        bytes=total,
        content_type=content_type,
    )
