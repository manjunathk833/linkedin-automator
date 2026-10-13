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
    source: str = Field(description="greenhouse | lever | ashby | workday | linkedin")
    company_name: str
    job_title: str
    location: str
    is_remote: bool = False
    is_dream_org: bool = Field(default=False, description="Flag indicating tier-1 dream company status")
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
    ats_provider: str = Field(description="greenhouse | lever | ashby | workday")
    slug: str
    domain: str | None = None
    active: bool = True
    industry: str | None = None
    is_dream_org: bool = Field(default=False, description="Whether company is tagged as an elite Dream Org")
    site: str | None = Field(default=None, description="Workday site name if applicable")
    datacenter: str | None = Field(default="wd3", description="Workday datacenter if applicable")
