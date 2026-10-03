"""
Normalized Data Schemas for Multi-Source Ingestion & Application Copilot.
Supports Greenhouse, Lever, Ashby, and LinkedIn postings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobListing(BaseModel):
    id: str = Field(description="Unique composite key: {source}_{company}_{external_id}")
    source: str = Field(description="greenhouse | lever | ashby | linkedin")
    company_name: str
    job_title: str
    location: str
    is_remote: bool = False
    job_description_raw: str
    job_description_clean: str
    url: str
    salary_range: str | None = None
    extracted_skills: list[str] = Field(default_factory=list)
    screening_questions: list[dict[str, Any]] = Field(default_factory=list)
    posted_at: datetime | None = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending", description="pending | approved | rejected | applied")


class TargetCompany(BaseModel):
    name: str
    ats_provider: str = Field(description="greenhouse | lever | ashby")
    slug: str
    domain: str | None = None
    active: bool = True
    industry: str | None = None
