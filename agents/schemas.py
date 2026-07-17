"""Pydantic schemas — every agent must return JSON that validates against one of these."""
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class Intent(BaseModel):
    intent: str = Field(description="One-sentence restatement of what the user wants")
    operation: str = Field(description="vlan_migration | vlan_change | delete_vlan | reboot | "
                                       "interface_change | config_change | diagnostic | other")
    target_customers: Optional[str] = None
    device: Optional[str] = None
    vlan: Optional[int] = None
    urgency: Literal["low", "normal", "high", "emergency"] = "normal"
    maintenance_window_required: bool = True


class PlanStep(BaseModel):
    step_id: int
    action: str
    tool: Optional[str] = None            # inventory | telemetry | knowledge | policy | execution | verification
    rollback_action: Optional[str] = None


class Plan(BaseModel):
    summary: str
    steps: list[PlanStep]


class ToolCall(BaseModel):
    tool: Literal["inventory", "telemetry", "knowledge"]
    query: Union[dict[str, Any], str]
    reason: str = ""


class ToolSelection(BaseModel):
    calls: list[ToolCall]


class RiskFactor(BaseModel):
    factor: str
    points: int


class RiskAssessment(BaseModel):
    base_score: int = Field(ge=0, le=100)
    base_reason: str
    adders: list[RiskFactor] = []
    risk_score: int = Field(ge=0, le=100)      # recomputed deterministically downstream
    risk_level: Literal["Low", "Medium", "High", "Critical"]
    business_impact: str
    estimated_downtime: str
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]


class ReviewerVerdict(BaseModel):
    verdict: Literal["approve", "modify", "reject"]
    adjusted_risk_level: Literal["Low", "Medium", "High", "Critical"]
    adjusted_risk_score: int = Field(ge=0, le=100)
    critique: str
    concerns: list[str] = []
    required_modifications: list[str] = []
    evidence_cited: list[str] = []
    consensus: str


class Explanation(BaseModel):
    decision: str
    confidence: float = Field(ge=0, le=1)
    evidence_cited: list[str]
    policies_checked: list[str]
    reasoning: str
    rollback_summary: str
    verification_plan: str
    recommendation: str


class ExecutiveSummary(BaseModel):
    summary: str
