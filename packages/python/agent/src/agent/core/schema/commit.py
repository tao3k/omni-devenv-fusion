# schema/commit.py
# Commit Authorization (Smart Commit Protocol)

from typing import List, Optional

from pydantic import BaseModel, Field


class CommitScopeValidation(BaseModel):
    """Validation result for commit scope."""

    scope: str = Field(..., description="Commit scope being validated")
    is_valid: bool = Field(..., description="Whether scope is valid in cog.toml")
    available_scopes: List[str] = Field(
        default_factory=list, description="List of valid scopes from cog.toml"
    )
    suggestion: Optional[str] = Field(None, description="Closest valid scope if current is invalid")


class CommitMessageValidation(BaseModel):
    """Complete commit message validation."""

    type: str = Field(..., description="Commit type (feat, fix, chore, etc.)")
    scope: str = Field(..., description="Commit scope")
    message: str = Field(..., description="Commit message body")
    is_valid: bool = Field(..., description="Whether message is valid")
    subject_length: int = Field(..., description="Subject line length")
    subject_valid: bool = Field(..., description="Subject follows conventional commits")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")


class CommitAuthorization(BaseModel):
    """Authorization token for smart commit."""

    auth_token: str = Field(..., description="One-time authorization token")
    expires_at: str = Field(..., description="Token expiration timestamp")
    commit_details: CommitMessageValidation = Field(..., description="Validated commit details")
    instructions: str = Field(..., description="Authorization instructions")


__all__ = ["CommitScopeValidation", "CommitMessageValidation", "CommitAuthorization"]
