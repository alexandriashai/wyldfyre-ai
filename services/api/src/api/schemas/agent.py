"""
Agent schemas for tools and capabilities.
"""

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """Information about a single tool available to an agent."""

    name: str = Field(..., description="Tool name identifier")
    description: str = Field(..., description="Human-readable tool description")
    category: str = Field(..., description="Tool category (e.g., file, git, network)")
    permission_level: int = Field(
        ...,
        ge=0,
        le=4,
        description="Required permission level (0=READ_ONLY to 4=SUPERUSER)",
    )


class AgentToolsResponse(BaseModel):
    """Response containing agent tools and capabilities."""

    agent_name: str = Field(..., description="Name of the agent")
    agent_type: str = Field(..., description="Type of agent")
    description: str = Field(..., description="Agent description")
    permission_level: int = Field(..., description="Agent's permission level")
    tools: list[ToolInfo] = Field(default_factory=list, description="Available tools")
    capabilities: list[str] = Field(
        default_factory=list, description="Agent capabilities"
    )
    allowed_capabilities: list[str] = Field(
        default_factory=list, description="Capability categories agent can use"
    )
