"""Shared Pydantic models for PhysBound MCP tool responses."""

from pydantic import BaseModel


class PhysBoundResult(BaseModel):
    """Base output envelope for all PhysBound tool responses."""

    human_readable: str
    latex: str
    warnings: list[str] = []
