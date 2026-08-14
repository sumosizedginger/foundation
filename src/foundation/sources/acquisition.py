from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from foundation.living_cost.manifest import RetrievedSourceArtifact
from foundation.sources.http import download_file

logger = logging.getLogger(__name__)

NON_RETRIEVED_STATUSES = {
    "SOURCE_GAP",
    "LICENSING_REVIEW",
    "PARSER_READY_NOT_RETRIEVED",
    "UNAVAILABLE",
}


def sidecar_path(destination: Path) -> Path:
    return destination.with_name(f"{destination.name}.provenance.json")


def write_retrieval_sidecar(
    destination: Path,
    *,
    source_id: str,
    url: str,
    retrieved_at: str,
    sha256: str,
    byte_size: int,
    http_status: int | None,
    content_type: str | None,
) -> Path:
    payload = {
        "source_id": source_id,
        "url": url,
        "retrieved_at": retrieved_at,
        "sha256": sha256,
        "byte_size": byte_size,
        "http_status": http_status,
        "content_type": content_type,
    }
    path = sidecar_path(destination)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def read_retrieval_sidecar(destination: Path) -> dict[str, Any] | None:
    path = sidecar_path(destination)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def record_unretrieved(
    source_id: str,
    *,
    status: str,
    notes: str,
    resolved_url: str = "",
) -> RetrievedSourceArtifact:
    if status not in NON_RETRIEVED_STATUSES:
        raise ValueError(f"record_unretrieved received unexpected status {status}")
    return RetrievedSourceArtifact(
        source_id=source_id,
        retrieved_at="",
        sha256="",
        byte_size=0,
        local_cache_filename="",
        validation_status=status,
        resolved_url=resolved_url,
        notes=notes,
    )


def provenance_is_complete(artifact: RetrievedSourceArtifact | None) -> bool:
    """Full VALIDATED requires a real retrieval sidecar, not just a hash of cached bytes."""
    if artifact is None:
        return False
    if not artifact.retrieved_at or not str(artifact.retrieved_at).strip():
        return False
    if not artifact.resolved_url or not str(artifact.resolved_url).strip():
        return False
    if not artifact.local_cache_filename or not str(artifact.local_cache_filename).strip():
        return False
    if not artifact.sha256 or len(artifact.sha256) != 64:
        return False
    return bool(artifact.byte_size)


def validation_status_after_parse(
    artifact: RetrievedSourceArtifact,
    *,
    parsed_ok: bool,
    parsed_status: str = "VALIDATED",
) -> str:
    """Never promote to VALIDATED without complete retrieval provenance."""
    if artifact.validation_status in NON_RETRIEVED_STATUSES:
        return artifact.validation_status
    if not parsed_ok:
        return artifact.validation_status or "RETRIEVED_UNVALIDATED"
    if not provenance_is_complete(artifact):
        return "INCOMPLETE_PROVENANCE"
    return parsed_status


def acquire_source(
    source_id: str,
    url: str,
    cache_dir: Path,
    expected_filename: str,
    *,
    force_download: bool = False,
    refresh_if_unprovenanced: bool = True,
    timeout: tuple[float, float] = (15.0, 180.0),
    max_bytes: int = 500_000_000,
) -> RetrievedSourceArtifact | None:
    """Acquire a source file via HTTP or reuse a cached copy with sidecar provenance.

    Cache hits never invent retrieved_at from filesystem mtime.
    Missing sidecar => RETRIEVED_UNVALIDATED at best.
    Prefer re-retrieval over inventing retrieved_at when refresh_if_unprovenanced=True.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / expected_filename

    if (
        refresh_if_unprovenanced
        and destination.exists()
        and read_retrieval_sidecar(destination) is None
    ):
        logger.info("Re-retrieving %s because cached bytes have no provenance sidecar", source_id)
        force_download = True

    if force_download or not destination.exists():
        logger.info("Downloading source %s from %s", source_id, url)
        try:
            res = download_file(
                url=url, destination=destination, timeout=timeout, max_bytes=max_bytes
            )
            retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
            write_retrieval_sidecar(
                destination,
                source_id=source_id,
                url=url,
                retrieved_at=retrieved_at,
                sha256=res.sha256,
                byte_size=res.bytes,
                http_status=200,
                content_type=res.content_type,
            )
            return RetrievedSourceArtifact(
                source_id=source_id,
                retrieved_at=retrieved_at,
                sha256=res.sha256,
                byte_size=res.bytes,
                local_cache_filename=expected_filename,
                validation_status="RETRIEVED_UNVALIDATED",
                resolved_url=url,
            )
        except (OSError, ValueError, RuntimeError, TypeError, requests.RequestException) as exc:
            logger.error("Failed to acquire source %s from %s: %s", source_id, url, exc)
            if destination.exists() and destination.stat().st_size > 0:
                logger.warning(
                    "Keeping existing cache for %s after failed refresh; "
                    "status will not be full VALIDATED without a sidecar.",
                    source_id,
                )
                force_download = False
            else:
                return None

    logger.info("Using cached source for %s at %s", source_id, destination)
    try:
        digest = hashlib.sha256()
        total_bytes = 0
        with destination.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
                total_bytes += len(chunk)
        computed_sha = digest.hexdigest()
    except (OSError, ValueError) as exc:
        logger.error("Failed to read cached source %s: %s", source_id, exc)
        return None

    sidecar = read_retrieval_sidecar(destination)
    if sidecar is None:
        return RetrievedSourceArtifact(
            source_id=source_id,
            retrieved_at="",
            sha256=computed_sha,
            byte_size=total_bytes,
            local_cache_filename=expected_filename,
            validation_status="RETRIEVED_UNVALIDATED",
            resolved_url=url,
            notes="Cache hit without provenance sidecar; retrieved_at unknown.",
        )

    stored_sha = str(sidecar.get("sha256") or "")
    stored_size = int(sidecar.get("byte_size") or 0)
    if stored_sha and stored_sha != computed_sha:
        logger.error(
            "Cached bytes for %s do not match sidecar SHA (%s vs %s)",
            source_id,
            computed_sha,
            stored_sha,
        )
        return None
    if stored_size and stored_size != total_bytes:
        logger.error(
            "Cached bytes for %s do not match sidecar size (%s vs %s)",
            source_id,
            total_bytes,
            stored_size,
        )
        return None

    return RetrievedSourceArtifact(
        source_id=source_id,
        retrieved_at=str(sidecar.get("retrieved_at") or ""),
        sha256=computed_sha,
        byte_size=total_bytes,
        local_cache_filename=expected_filename,
        validation_status="RETRIEVED_UNVALIDATED",
        resolved_url=str(sidecar.get("url") or url),
    )
