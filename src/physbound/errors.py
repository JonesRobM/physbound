"""PhysBound error types with LaTeX-formatted physics violation explanations."""

from dataclasses import dataclass


@dataclass
class PhysicalViolationError(Exception):
    """Raised when an input or claim violates a physical law or hard limit.

    Always carries a LaTeX explanation suitable for rendering in technical documents.
    """

    message: str
    law_violated: str
    latex_explanation: str
    computed_limit: float | None = None
    claimed_value: float | None = None
    unit: str = ""

    def __str__(self) -> str:
        return f"[{self.law_violated}] {self.message}"

    def to_dict(self) -> dict:
        """Serialize for JSON MCP response."""
        return {
            "error": True,
            "violation_type": "PhysicalViolationError",
            "law_violated": self.law_violated,
            "message": self.message,
            "latex": self.latex_explanation,
            "computed_limit": self.computed_limit,
            "claimed_value": self.claimed_value,
            "unit": self.unit,
        }
