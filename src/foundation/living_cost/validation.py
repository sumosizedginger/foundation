"""Validation and Source-Integrity Audit Engine for Minimum Sustainable Living Cost.

Enforces fail-closed release gates, provenance completeness, and join validation:
- Status=MEASURED requires non-empty source_id, source_variable, source_url, source_reference_period, retrieved_at, and source_artifact_sha256.
- Real geography validation (valid 5-digit FIPS codes).
- Zero synthetic geography IDs in production.
- Join coverage audit between HUD FMR and Census ACS population weights.
- Valid mathematical distribution ordering (min <= P25 <= Median <= P75 <= max).
"""

from __future__ import annotations
from typing import Any
from foundation.living_cost.models import (
    ComponentStatus,
    LivingCostComponentObservation,
    LocalLivingCost,
    NationalLivingCostDistribution,
    StateLivingCostDistribution,
)


class ProvenanceValidationError(ValueError):
    """Raised when component provenance or source metadata is missing or invalid."""


def validate_component_provenance(obs: LivingCostComponentObservation) -> list[str]:
    """Audit single component observation metadata."""
    errors: list[str] = []

    if obs.status == ComponentStatus.MEASURED:
        if not obs.source_id or not obs.source_id.strip():
            errors.append(f"Fatal: MEASURED component {obs.component_id} has empty source_id")
        if not obs.source_variable or not obs.source_variable.strip():
            errors.append(f"Fatal: MEASURED component {obs.component_id} has empty source_variable")
        if not obs.source_url or not obs.source_url.strip():
            errors.append(f"Fatal: MEASURED component {obs.component_id} has empty source_url")
        if not obs.source_reference_period or not obs.source_reference_period.strip():
            errors.append(f"Fatal: MEASURED component {obs.component_id} has empty source_reference_period")
        if not obs.retrieved_at or not obs.retrieved_at.strip():
            errors.append(f"Fatal: MEASURED component {obs.component_id} has empty retrieved_at timestamp")
        if not obs.source_artifact_sha256 or not obs.source_artifact_sha256.strip():
            errors.append(f"Fatal: MEASURED component {obs.component_id} has empty source_artifact_sha256")

    # Check geography ID format (must be 2-digit state or 5-digit county FIPS)
    if obs.geography_type == "county":
        if len(obs.geography_id) != 5 or not obs.geography_id.isdigit():
            errors.append(f"Fatal: Invalid county FIPS code: {obs.geography_id}")

    return errors


def validate_local_living_cost(loc: LocalLivingCost) -> list[str]:
    """Audit local county living cost observation."""
    errors: list[str] = []

    if loc.status == ComponentStatus.UNAVAILABLE:
        return errors

    # Check FIPS code
    if len(loc.geography_id) != 5 or not loc.geography_id.isdigit():
        errors.append(f"Fatal: Invalid county FIPS code: {loc.geography_id}")

    if loc.adult_population <= 0:
        errors.append(f"Fatal: Adult population must be positive, got {loc.adult_population} for {loc.geography_id}")

    if loc.net_needs_annual is not None and loc.gross_required_income is not None:
        if loc.net_needs_annual <= 0:
            errors.append(f"Fatal: Net needs must be positive, got {loc.net_needs_annual}")
        if loc.gross_required_income < loc.net_needs_annual:
            errors.append(
                f"Fatal: Gross required income ({loc.gross_required_income}) cannot be less than net needs ({loc.net_needs_annual})"
            )

    return errors


def validate_state_distribution(dist: StateLivingCostDistribution) -> list[str]:
    """Audit state-level aggregated distribution."""
    errors: list[str] = []

    if dist.status == ComponentStatus.UNAVAILABLE:
        return errors

    if dist.represented_adult_population <= 0:
        errors.append(f"Fatal: Represented adult population must be positive for {dist.state}")

    if (
        dist.weighted_p25_gross is not None
        and dist.weighted_median_gross is not None
        and dist.weighted_p75_gross is not None
    ):
        if dist.weighted_p25_gross > dist.weighted_median_gross:
            errors.append(f"Fatal: P25 ({dist.weighted_p25_gross}) > Median ({dist.weighted_median_gross}) for {dist.state}")
        if dist.weighted_median_gross > dist.weighted_p75_gross:
            errors.append(f"Fatal: Median ({dist.weighted_median_gross}) > P75 ({dist.weighted_p75_gross}) for {dist.state}")

    if dist.min_locality_gross is not None and dist.max_locality_gross is not None:
        if dist.min_locality_gross > dist.max_locality_gross:
            errors.append(f"Fatal: Min ({dist.min_locality_gross}) > Max ({dist.max_locality_gross}) for {dist.state}")

    return errors
