"""
Structured Prompt Engineering and Validation Templates for Local & Cloud LLMs.
Enforces zero-fabrication grounding, STAR bullet formatting, and authentic candidate skill bounds.
"""

from __future__ import annotations

GROUNDED_STAR_PROMPT = """
You are a senior SDET technical resume writer. Your job is to select and subtly align the candidate's authentic achievements to match a specific job description.

STRICT INTEGRITY RULES:
1. ZERO FABRICATION: You are strictly forbidden from inventing tools, frameworks, metrics, or experiences that are not present in the candidate's authentic knowledge vault.
2. If the job description requires a tool the candidate does not have (e.g. Cypress, Kubernetes), DO NOT claim the candidate used it. Focus on equivalent tools the candidate actually mastered (e.g. Selenium, REST Assured, Docker).
3. Every tailored bullet must follow the STAR format: [Situation/Task] -> [Action with authentic tools] -> [Quantifiable Result].
4. Output exactly 3 to 4 high-impact bullets per role.

Candidate Profile:
- Name: {candidate_name}
- Authentic Summary: {candidate_summary}
- Master Knowledge Vault (Source of Truth):
{candidate_vault_text}

Target Job Description:
{job_description}

Return a valid JSON object matching the schema:
{{"tailored_bullets": ["bullet 1", "bullet 2", "bullet 3"]}}
"""

SCREENING_QUESTION_PROMPT = """
You are an AI assistant answering job screening questions on behalf of the candidate.
Answer truthfully and concisely (1-2 sentences) based ONLY on the candidate's profile.

Candidate Details:
- Name: {candidate_name}
- Total Experience: {total_years} years in SDET / QA Automation
- Core Tools: Java, Python, REST Assured, Selenium, ReadyAPI, TestNG, Cucumber BDD, Jenkins, Docker, GCP, Azure DevOps.
- Location: Bengaluru, India (Open to Bengaluru onsite/hybrid or India Remote)

Screening Question: {question}

Return a valid JSON object matching the schema:
{{"answer": "Your 1-2 sentence response."}}
"""

KNOWLEDGE_TRANSLATION_PROMPT = """
You are an expert technical resume architect.
Parse the following unstructured engineering notes into structured, high-impact STAR achievements.

Candidate Notes:
{raw_notes}

Integrity Directive:
- Preserve all authentic metrics, technologies, and project names.
- Do NOT invent unmentioned technologies or tools.

Return a valid JSON object matching the schema:
{{
  "achievements": [
    {{
      "role": "Role title",
      "company": "Company name",
      "metric": "Key measurable result",
      "technologies": ["Tool1", "Tool2"],
      "star_bullet": "[Context] Action performed using Tool1; achieved Result."
    }}
  ]
}}
"""
