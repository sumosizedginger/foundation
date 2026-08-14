from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from foundation.living_cost.manifest import RetrievedSourceArtifact
from foundation.sources.http import download_file

logger = logging.getLogger(__name__)


def acquire_source(
    source_id: str,
    url: str,
    cache_dir: Path,
    expected_filename: str,
    *,
    force_download: bool = False,
    timeout: tuple[float, float] = (15.0, 180.0),
    max_bytes: int = 500_000_000,
) -> Optional[RetrievedSourceArtifact]:
    """
    Acquire a source file via HTTP or use the cached version.
    Returns a RetrievedSourceArtifact if successful, or None if unavailable/fails.
    """
    destination = cache_dir / expected_filename

    # If force_download is True, or file doesn't exist, we attempt download
    if force_download or not destination.exists():
        logger.info(f"Downloading source {source_id} from {url}...")
        try:
            res = download_file(
                url=url, destination=destination, timeout=timeout, max_bytes=max_bytes
            )
            retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
            logger.info(
                f"Successfully downloaded {source_id}: {res.bytes} bytes, SHA256 {res.sha256}"
            )
            return RetrievedSourceArtifact(
                source_id=source_id,
                retrieved_at=retrieved_at,
                sha256=res.sha256,
                byte_size=res.bytes,
                local_cache_filename=expected_filename,
                validation_status="RETRIEVED_UNVALIDATED",
            )
        except Exception as e:
            logger.error(f"Failed to acquire source {source_id} from {url}: {e}")
            return None

    # If it exists and we didn't force download, we compute hash and return it
    # We must treat the file's current modified time as retrieved_at for now,
    # or ideally we'd store provenance sidecars. But for Deliverable 1, we compute from bytes.
    logger.info(f"Using cached source for {source_id} at {destination}")
    try:
        import hashlib

        digest = hashlib.sha256()
        total_bytes = 0
        with destination.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
                total_bytes += len(chunk)

        mtime = destination.stat().st_mtime
        retrieved_at = datetime.fromtimestamp(mtime, tz=UTC).replace(microsecond=0).isoformat()

        return RetrievedSourceArtifact(
            source_id=source_id,
            retrieved_at=retrieved_at,
            sha256=digest.hexdigest(),
            byte_size=total_bytes,
            local_cache_filename=expected_filename,
            validation_status="RETRIEVED_UNVALIDATED",
        )
    except Exception as e:
        logger.error(f"Failed to read cached source {source_id}: {e}")
        return None
