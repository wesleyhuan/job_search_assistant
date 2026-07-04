"""Pydantic schemas for structured resume data.

Design note: this module is the single source of truth for what a
"structured resume" looks like. The MCP server exposes this schema as a
resource so the LLM agent knows the exact JSON shape to produce, and the
`validate_resume` tool uses the same models to verify the agent's output.
Keeping schema definition, exposure, and validation in one place prevents
the three from drifting apart.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactInfo(BaseModel):
    """Candidate contact details. Only `name` is mandatory because many
    resumes omit phone/links, and we don't want validation to fail on
    legitimately sparse documents."""

    name: str = Field(..., min_length=1, description="Full name of the candidate")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number, any format")
    location: Optional[str] = Field(None, description="City / country")
    links: list[str] = Field(
        default_factory=list,
        description="Personal links: LinkedIn, GitHub, portfolio, etc.",
    )


class Education(BaseModel):
    """One education entry (degree, school, period)."""

    institution: str = Field(..., description="School / university name")
    degree: Optional[str] = Field(None, description="Degree name, e.g. 'B.S. Computer Science'")
    start_date: Optional[str] = Field(None, description="YYYY or YYYY-MM")
    end_date: Optional[str] = Field(None, description="YYYY, YYYY-MM, or 'present'")


class Experience(BaseModel):
    """One work-experience entry."""

    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    start_date: Optional[str] = Field(None, description="YYYY or YYYY-MM")
    end_date: Optional[str] = Field(None, description="YYYY, YYYY-MM, or 'present'")
    highlights: list[str] = Field(
        default_factory=list,
        description="Bullet points describing achievements in this role",
    )

    @field_validator("highlights")
    @classmethod
    def strip_empty_highlights(cls, v: list[str]) -> list[str]:
        # LLMs sometimes emit empty strings when a bullet is ambiguous;
        # silently dropping them is safer than failing the whole resume.
        return [h.strip() for h in v if h and h.strip()]


class Resume(BaseModel):
    """Top-level structured resume.

    `skills` is a flat list rather than categorized (languages/tools/etc.)
    on purpose: categorization is subjective and varies per resume, so we
    let the downstream Job Matcher agent do its own grouping.
    """

    contact: ContactInfo
    summary: Optional[str] = Field(None, description="Professional summary paragraph")
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list, description="Flat list of skills")
    languages: list[str] = Field(
        default_factory=list, description="Spoken languages, e.g. 'Mandarin (native)'"
    )
