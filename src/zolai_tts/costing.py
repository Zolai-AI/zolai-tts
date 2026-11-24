"""Cost intelligence: tier classification, per-call estimates, and budgets.

Prices come only from data the providers actually publish: the `:free` id
suffix on OpenRouter, an explicit pricing block on a catalog entry, or the
curated :data:`zolai_tts.catalog.MODEL_PRICING` table (which carries a source
and an as-of date). When nothing is published the estimate is ``None`` with a
note pointing at the pricing page — this module never invents a rate, and the
UI is expected to attribute the number rather than assert it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .catalog import MODEL_PRICING, estimate_cost_usd, model_tier

Tier = str  # "free" | "free-local" | "paid" | "unknown"

FREE_MODEL_HINTS = (":free",)  # OpenRouter's official free-tier signal


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def classify_tier(model: dict[str, Any], provider: str = "") -> Tier:
    """free / paid from the slug, a published pricing block, or the catalog rule."""
    slug = str(model.get("id") or model.get("slug") or "")
    if any(hint in slug for hint in FREE_MODEL_HINTS):
        return "free"
    pricing = model.get("pricing") or {}
    rates = [_dec(v) for v in pricing.values() if isinstance(pricing, dict)]
    rates = [r for r in rates if r is not None]
    if rates:
        return "free" if all(rate == 0 for rate in rates) else "paid"
    if provider:
        rule = model_tier(provider, slug)
        return rule or "unknown"
    return str(model.get("tier") or "unknown")


@dataclass
class Estimate:
    provider: str
    model: str
    tier: Tier
    characters: int
    usd: Decimal | None  # None = not publishable from known data
    basis: str
    source: str = ""  # where the price came from (catalog field or curated table entry)

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier,
            "characters": self.characters,
            "estimated_usd": float(self.usd) if self.usd is not None else None,
            "basis": self.basis,
            "price_source": self.source or None,
        }


def estimate_cost(
    provider: str,
    text: str,
    model: dict[str, Any] | None = None,
) -> Estimate:
    """Cost for one call. Exact catalog/curated prices first, otherwise unknown."""
    model = model or {}
    slug = str(model.get("id") or model.get("slug") or "")
    tier = classify_tier(model, provider)
    characters = len(text)

    if tier in ("free", "free-local"):
        return Estimate(
            provider, slug, tier, characters, Decimal("0"), f"{tier} tier — no per-request cost"
        )

    pricing = model.get("pricing") or {}
    per_character = _dec(pricing.get("characters") or pricing.get("per_character"))
    if per_character is not None and per_character > 0:
        return Estimate(
            provider,
            slug,
            tier,
            characters,
            (per_character * characters).quantize(Decimal("0.00000001")),
            "catalog per-character price",
            "provider catalog",
        )

    if slug in MODEL_PRICING or (provider and tier == "paid"):
        usd, note = estimate_cost_usd(provider, slug or None, text, tier)
        curated = MODEL_PRICING.get(slug, {}) if slug else {}
        source = str(curated.get("source") or "") or (
            "provider pricing page" if usd is None else ""
        )
        if usd is not None:
            return Estimate(provider, slug, tier, characters, Decimal(str(usd)), note, source)
        return Estimate(provider, slug, tier, characters, None, note, source)

    return Estimate(provider, slug, tier, characters, None, "no published price for this model")


def actual_cost(record: dict[str, Any]) -> Decimal | None:
    """Normalize whatever a provider returned for one run into USD."""
    for key in ("cost_usd", "cost", "usage_cost_usd"):
        if record.get(key) is not None:
            return _dec(record[key])
    usage = record.get("usage") or {}
    if isinstance(usage, dict):
        for key in ("total_usd", "cost_usd", "usd"):
            if usage.get(key) is not None:
                return _dec(usage.get(key))
    return None


# --------------------------------------------------------------------- budgets


@dataclass
class BudgetLimits:
    daily_usd: float = 0.0  # 0 = unlimited
    monthly_usd: float = 0.0
    free_only: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BudgetLimits:
        data = data or {}
        return cls(
            daily_usd=max(0.0, float(data.get("daily_usd") or 0.0)),
            monthly_usd=max(0.0, float(data.get("monthly_usd") or 0.0)),
            free_only=bool(data.get("free_only")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "daily_usd": self.daily_usd,
            "monthly_usd": self.monthly_usd,
            "free_only": self.free_only,
        }


def check_budget(
    limits: BudgetLimits, spend_today: float, spend_month: float, planned: float | None
) -> dict[str, Any]:
    """Pre-flight gate: is this call allowed, and will it cross a limit?

    An unknown price (`planned is None`) is allowed unless free-only is on, in
    which case only provably free tiers pass.
    """
    reasons: list[str] = []
    planned_value = planned or 0.0
    if limits.free_only and planned is None:
        reasons.append("free-only mode is on and this model has no published price")
    elif limits.free_only and planned_value > 0:
        reasons.append("free-only mode is on and this call is billed")
    if limits.daily_usd and spend_today + planned_value > limits.daily_usd:
        reasons.append(f"daily: {spend_today + planned_value:.6f} > {limits.daily_usd:.6f} USD")
    if limits.monthly_usd and spend_month + planned_value > limits.monthly_usd:
        reasons.append(f"monthly: {spend_month + planned_value:.6f} > {limits.monthly_usd:.6f} USD")
    return {
        "allowed": not reasons,
        "reasons": reasons,
        "planned_usd": planned,
        "spent_today_usd": round(spend_today, 6),
        "spent_month_usd": round(spend_month, 6),
        "limits": limits.as_dict(),
        "checked_at": datetime.now(UTC).isoformat(),
    }
