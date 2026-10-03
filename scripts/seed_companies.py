"""
Seed generator for target tech enterprises and high-growth startups hiring Senior SDETs.
Outputs curated registry to data/config/target_companies.json with ATS board slugs.
"""

from __future__ import annotations

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_CONFIG_DIR = os.path.join(PROJECT_ROOT, "data", "config")
CONFIG_FILE = os.path.join(TARGET_CONFIG_DIR, "target_companies.json")

SEED_COMPANIES = [
    # --- Greenhouse Boards ---
    {
        "name": "Postman",
        "ats_provider": "greenhouse",
        "slug": "postman",
        "domain": "postman.com",
        "industry": "Developer Tools",
    },
    {
        "name": "BrowserStack",
        "ats_provider": "greenhouse",
        "slug": "browserstack",
        "domain": "browserstack.com",
        "industry": "Testing Infrastructure",
    },
    {
        "name": "Razorpay",
        "ats_provider": "greenhouse",
        "slug": "razorpay",
        "domain": "razorpay.com",
        "industry": "Fintech",
    },
    {
        "name": "Cloudflare",
        "ats_provider": "greenhouse",
        "slug": "cloudflare",
        "domain": "cloudflare.com",
        "industry": "Cloud Security",
    },
    {
        "name": "Databricks",
        "ats_provider": "greenhouse",
        "slug": "databricks",
        "domain": "databricks.com",
        "industry": "Data & AI",
    },
    {"name": "Stripe", "ats_provider": "greenhouse", "slug": "stripe", "domain": "stripe.com", "industry": "Payments"},
    {"name": "Figma", "ats_provider": "greenhouse", "slug": "figma", "domain": "figma.com", "industry": "Design Tech"},
    {"name": "GitLab", "ats_provider": "greenhouse", "slug": "gitlab", "domain": "gitlab.com", "industry": "DevOps"},
    {
        "name": "Coinbase",
        "ats_provider": "greenhouse",
        "slug": "coinbase",
        "domain": "coinbase.com",
        "industry": "Crypto / Fintech",
    },
    {
        "name": "Thoughtworks",
        "ats_provider": "greenhouse",
        "slug": "thoughtworks",
        "domain": "thoughtworks.com",
        "industry": "Consulting & QA",
    },
    {
        "name": "Instacart",
        "ats_provider": "greenhouse",
        "slug": "instacart",
        "domain": "instacart.com",
        "industry": "E-Commerce",
    },
    {
        "name": "Okta",
        "ats_provider": "greenhouse",
        "slug": "okta",
        "domain": "okta.com",
        "industry": "Identity & Security",
    },
    {
        "name": "Rubrik",
        "ats_provider": "greenhouse",
        "slug": "rubrik",
        "domain": "rubrik.com",
        "industry": "Data Security",
    },
    {
        "name": "DoorDash",
        "ats_provider": "greenhouse",
        "slug": "doordash",
        "domain": "doordash.com",
        "industry": "Delivery / Logistics",
    },
    {
        "name": "Elastic",
        "ats_provider": "greenhouse",
        "slug": "elastic",
        "domain": "elastic.co",
        "industry": "Search & Observability",
    },
    {
        "name": "Twilio",
        "ats_provider": "greenhouse",
        "slug": "twilio",
        "domain": "twilio.com",
        "industry": "Communications API",
    },
    {
        "name": "HashiCorp",
        "ats_provider": "greenhouse",
        "slug": "hashicorp",
        "domain": "hashicorp.com",
        "industry": "Infrastructure",
    },
    {
        "name": "MongoDB",
        "ats_provider": "greenhouse",
        "slug": "mongodb",
        "domain": "mongodb.com",
        "industry": "Database",
    },
    {
        "name": "Confluent",
        "ats_provider": "greenhouse",
        "slug": "confluent",
        "domain": "confluent.io",
        "industry": "Event Streaming",
    },
    {
        "name": "Snowflake",
        "ats_provider": "greenhouse",
        "slug": "snowflake",
        "domain": "snowflake.com",
        "industry": "Cloud Data Platform",
    },
    # --- Lever Boards ---
    {
        "name": "Docker",
        "ats_provider": "lever",
        "slug": "docker",
        "domain": "docker.com",
        "industry": "Containers & Cloud",
    },
    {"name": "Canva", "ats_provider": "lever", "slug": "canva", "domain": "canva.com", "industry": "Design"},
    {"name": "Plaid", "ats_provider": "lever", "slug": "plaid", "domain": "plaid.com", "industry": "Fintech API"},
    {
        "name": "Spotify",
        "ats_provider": "lever",
        "slug": "spotify",
        "domain": "spotify.com",
        "industry": "Audio & Media",
    },
    {
        "name": "Hotstar",
        "ats_provider": "lever",
        "slug": "hotstar",
        "domain": "hotstar.com",
        "industry": "Streaming Media",
    },
    {
        "name": "Palantir",
        "ats_provider": "lever",
        "slug": "palantir",
        "domain": "palantir.com",
        "industry": "Data Analytics",
    },
    {
        "name": "Deliveroo",
        "ats_provider": "lever",
        "slug": "deliveroo",
        "domain": "deliveroo.co.uk",
        "industry": "Delivery",
    },
    {"name": "Kite", "ats_provider": "lever", "slug": "kite", "domain": "kite.com", "industry": "AI Developer Tools"},
    {
        "name": "Grammarly",
        "ats_provider": "lever",
        "slug": "grammarly",
        "domain": "grammarly.com",
        "industry": "AI Writing",
    },
    # --- Ashby Boards ---
    {
        "name": "Linear",
        "ats_provider": "ashby",
        "slug": "linear",
        "domain": "linear.app",
        "industry": "Product Management",
    },
    {
        "name": "Ramp",
        "ats_provider": "ashby",
        "slug": "ramp",
        "domain": "ramp.com",
        "industry": "Corporate Cards / Fintech",
    },
    {
        "name": "Retool",
        "ats_provider": "ashby",
        "slug": "retool",
        "domain": "retool.com",
        "industry": "Internal Tooling",
    },
    {"name": "Vercel", "ats_provider": "ashby", "slug": "vercel", "domain": "vercel.com", "industry": "Web Deployment"},
    {
        "name": "Scale AI",
        "ats_provider": "ashby",
        "slug": "scaleai",
        "domain": "scale.com",
        "industry": "Data Infrastructure for AI",
    },
    {
        "name": "Airtable",
        "ats_provider": "ashby",
        "slug": "airtable",
        "domain": "airtable.com",
        "industry": "No-Code Database",
    },
    {
        "name": "Zapier",
        "ats_provider": "ashby",
        "slug": "zapier",
        "domain": "zapier.com",
        "industry": "Automation Platform",
    },
    {
        "name": "Notion",
        "ats_provider": "ashby",
        "slug": "notion",
        "domain": "notion.so",
        "industry": "Workspace & Docs",
    },
]


def seed_target_companies():
    os.makedirs(TARGET_CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(SEED_COMPANIES, f, indent=2)
    print(f"✅ Target company registry seeded with {len(SEED_COMPANIES)} enterprises at: {CONFIG_FILE}")


if __name__ == "__main__":
    seed_target_companies()
