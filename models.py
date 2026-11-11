"""Structured types for the vendor desk agent."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class VendorDecision(BaseModel):
    """What the agent returns for one vendor document (handbook section 13)."""

    vendor: Optional[str] = Field(description="Vendor name as written in the document. null if not stated.")
    sku: Optional[str] = Field(
        description="Campus Customs SKU, e.g. CC-HD-006. null if the document does not give one."
    )
    unit_price: Optional[float] = Field(
        description="Quoted unit price in US dollars. null if the document does not say."
    )
    lead_time_days: Optional[int] = Field(
        description="Lead time in days, as the number stated in the document. null if not stated."
    )
    min_order: Optional[int] = Field(
        description="Minimum order in units. null if the document does not say."
    )
    decision: Literal["recommend", "do_not_recommend"] = Field(
        description="recommend only if all four handbook purchasing checks pass."
    )
    reason: str = Field(
        description="One sentence that names the purchasing check that decided it."
    )


class ExtractedFacts(BaseModel):
    """DESIGN layer: what the model is allowed to return. Facts only, no decision,
    no free text, so a document cannot steer the decision or plant a link."""

    vendor: Optional[str] = Field(description="Vendor name as written in the document. null if not stated.")
    sku: Optional[str] = Field(description="Campus Customs SKU, e.g. CC-HD-006. null if not stated.")
    unit_price: Optional[float] = Field(description="Quoted unit price in US dollars. null if not stated.")
    lead_time_days: Optional[int] = Field(description="Lead time in days as stated. null if not stated.")
    min_order: Optional[int] = Field(description="Minimum order in units. null if not stated.")
