"""
Synthetic Mock Fixture Generator for Clean CI & Isolated Environments.
Provides zero-secret, anonymized test fixtures for regression testing without
requiring private candidate PII or real credentials in Git.
"""

from __future__ import annotations

import json
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_mock_candidate_master_data() -> dict:
    return {
        "personal": {
            "full_name": "Test Candidate",
            "first_name": "Test",
            "last_name": "Candidate",
            "email": "test.candidate@example.com",
            "phone": "+910000000000",
            "phone_country_code": "+91",
            "address_line1": "123 Mock Boulevard",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
            "postal_code": "560001",
            "location": "Bengaluru, Karnataka, India",
            "prefix": "Mr.",
            "workday_default_password": "TEST_MOCK_PASSWORD_123!",
        },
        "profiles": {
            "linkedin": "https://www.linkedin.com/in/test-candidate/",
            "github": "https://github.com/test-candidate",
            "portfolio": "https://example.com/portfolio",
            "twitter": "",
        },
        "current_employment": {
            "company": "Value Labs",
            "title": "Senior Engineer - QE",
            "start_date": "2023-06-01",
            "is_current": True,
            "location": "Bengaluru, India",
        },
        "previous_employments": [
            {
                "company": "Dunzo",
                "title": "SDET-1",
                "start_date": "2022-08-01",
                "end_date": "2023-06-30",
                "location": "Bengaluru, India",
            },
            {
                "company": "Tata Elxsi",
                "title": "Software Engineer",
                "start_date": "2019-03-01",
                "end_date": "2022-08-01",
                "location": "Bengaluru, India",
            },
        ],
        "education": {
            "institution": "Visvesvaraya Technological University",
            "degree": "B.E.",
            "field_of_study": "Computer Science (Information Science)",
            "start_date": "2014-08-01",
            "end_date": "2018-06-01",
            "gpa": "CGPA: 8.02 / 10",
        },
    }


def get_mock_resume_profile() -> dict:
    return {
        "personal_details": {
            "full_name": "Test Candidate",
            "label": "Senior SDET | API & UI Automation | Java, Python, Microservices",
            "email": "test.candidate@example.com",
            "phone": "+910000000000",
            "location": "Bengaluru, Karnataka, India",
            "summary": "Senior SDET with 7 years of experience engineering scalable API and UI automation frameworks across Airline, Quick-Commerce, and OTT microservice architectures. Expert in Java, Python, REST Assured, Selenium, and CI/CD integration.",
            "profiles": [
                {
                    "network": "LinkedIn",
                    "username": "test-candidate",
                    "url": "https://www.linkedin.com/in/test-candidate/",
                },
                {
                    "network": "GitHub",
                    "username": "test-candidate",
                    "url": "https://github.com/test-candidate",
                },
            ],
        },
        "experience_history": [
            {
                "role": "Senior Engineer - QE",
                "company": "Value Labs",
                "company_url": None,
                "start_date": "2023-06-01",
                "end_date": None,
                "summary": "",
                "achievements": [
                    "Mosaic Order Automation Framework: Architected UI and API automation frameworks for 6+ airline projects leveraging REST Assured, Selenium, and BDD; built 1500+ test cases, reducing execution effort from 1,125 to 125 man-hours (90% reduction). Integrated with Harness CI/CD pipelines to run and monitor daily and weekly runs for smoke and regression suites.",
                    "Log Monitoring & Tooling: Automated daily error log analysis in Kibana for 30+ microservices for 6+ projects leveraging AI for implementation, detecting 2–4 critical bugs prior to each release. Built internal productivity tools integrating Azure DevOps APIs and release dashboards to track effort and team compliance.",
                    "AI Initiatives: Designed Agents using Copilot which leveraged AI to automate STLC processes with Azure DevOps, Maven Integration allowing the team to fast track STLC further reducing delivery time by 60%.",
                ],
                "tech_tags": [
                    "REST Assured",
                    "Selenium",
                    "BDD",
                    "Harness",
                    "Kibana",
                    "Azure DevOps",
                    "Copilot",
                    "Maven",
                    "Java",
                ],
            },
            {
                "role": "SDET-1",
                "company": "Dunzo",
                "company_url": None,
                "start_date": "2022-08-01",
                "end_date": "2023-06-30",
                "summary": "",
                "achievements": [
                    "Automated end-to-end API flows and DB validations using the Ekam Java Framework for 4 key features, achieving 60% test coverage in a microservices-based Merchant Service suite.",
                    "Designed and maintained resilient regression suites using Postman, Newman, and Jenkins, enabling continuous daily validation for critical payment and order flows.",
                    "Streamlined QA release sign-offs by collaborating in Agile sprints, performing rigorous root-cause analysis, and logging actionable defects in Jira.",
                ],
                "tech_tags": [
                    "Ekam",
                    "Java",
                    "REST API",
                    "PostgreSQL",
                    "Microservices",
                    "Postman",
                    "Newman",
                    "Jenkins",
                    "Jira",
                ],
            },
            {
                "role": "Software Engineer",
                "company": "Tata Elxsi",
                "company_url": None,
                "start_date": "2019-03-01",
                "end_date": "2022-08-01",
                "summary": "",
                "achievements": [
                    "Falcon OTT Test Automation: Engineered automated test suites in Python, Appium, and PyTest for a multi-platform OTT application, improving test efficiency by 40% across Web, Android, iOS, and Smart TVs.",
                    "CI/CD Integration: Configured Git and Jenkins pipelines for automated test execution, eliminating 15 hours of manual testing effort per sprint release.",
                    "Defect Lifecycle Management: Authored 300+ comprehensive test scenarios, tracked defects in Bugzilla, and conducted cross-functional defect triage with development and product leads.",
                ],
                "tech_tags": [
                    "Python",
                    "PyTest",
                    "Selenium",
                    "Appium",
                    "Jenkins",
                    "Git",
                    "Bugzilla",
                    "Jira",
                ],
            },
        ],
        "education": [
            {
                "institution": "Visvesvaraya Technological University",
                "area": "Computer Science (Information Science)",
                "study_type": "B.E.",
                "start_date": "2014-08-01",
                "end_date": "2018-06-01",
                "gpa": "CGPA: 8.02 / 10",
                "courses": [],
            }
        ],
        "projects": [
            {
                "name": "LSY - API + UI Automation (ValueLabs)",
                "description": "Architected and automated around 300+ test cases, migrating 12+ services in a microservice architecture with UI payment automation.",
                "url": None,
                "start_date": "2026-01-01",
                "end_date": None,
                "highlights": [
                    "Architected and automated around 300+ test cases across 12+ microservices.",
                    "Added UI automation for end-to-end payment flows.",
                    "Reduced automation effort by 75% utilizing AI.",
                ],
                "tech_tags": [
                    "REST Assured",
                    "Selenium",
                    "Copilot",
                    "Harness",
                    "Java",
                    "BDD",
                ],
            },
            {
                "name": "SSR - Special Service Requests (ValueLabs)",
                "description": "Airline domain project for adding Special Service Requests (SSRs) to PNRs across diverse business scenarios.",
                "url": None,
                "start_date": "2024-01-01",
                "end_date": "2026-01-01",
                "highlights": [
                    "Automated over 300+ API test cases for airline Special Service Request workflows.",
                ],
                "tech_tags": ["REST Assured", "Harness", "Java", "BDD"],
            },
            {
                "name": "Dunzo Merchant Service (Dunzo)",
                "description": "Owned and automated Dunzo Merchant Service flows across distributed microservices.",
                "url": None,
                "start_date": "2022-08-01",
                "end_date": "2023-06-30",
                "highlights": [
                    "Automated API and database validation flows using Ekam Java Framework.",
                ],
                "tech_tags": [
                    "Ekam Framework",
                    "Java",
                    "Kubernetes",
                    "Jenkins",
                    "PostgreSQL",
                ],
            },
            {
                "name": "OTT Streaming Platform (Tata Elxsi)",
                "description": "End-to-end testing and automation for Web, iOS, Android, and TV platforms.",
                "url": None,
                "start_date": "2019-12-09",
                "end_date": "2022-08-31",
                "highlights": [
                    "Performed end-to-end testing for Mobile iOS and Android platforms using Appium.",
                ],
                "tech_tags": ["Appium", "Python", "Charles Proxy", "Postman"],
            },
        ],
        "skills_matrix": {
            "API Automation": [
                "REST Assured",
                "ReadyAPI",
                "TestNG",
                "Cucumber BDD",
                "Postman",
                "WireMock",
                "Pact",
                "Kafka",
            ],
            "Languages & UI Automation": [
                "Java",
                "Python",
                "TypeScript",
                "Selenium",
                "Playwright",
                "Appium",
            ],
            "CI/CD & Infra": [
                "Jenkins",
                "GitHub Actions",
                "Azure DevOps",
                "Docker",
                "Kubernetes",
                "GCP",
                "TeamCity",
                "Harness",
            ],
            "Observability & Tools": ["Kibana", "Grafana", "Allure", "Jira", "Maven"],
        },
        "certifications": [
            {
                "name": "Rest API Testing (Automation) from Scratch-Rest Assured Java",
                "issuer": "Udemy",
                "issue_date": "2023-01-01",
                "expiry_date": None,
                "credential_id": None,
                "url": None,
            }
        ],
        "awards": [
            {
                "title": "Spark Award",
                "awarder": "ValueLabs",
                "award_date": "2024-03-01",
                "summary": "Recognized for exceptional automation contribution",
            }
        ],
        "languages": [
            {"language": "English", "fluency": "professional"},
            {"language": "Kannada", "fluency": "native"},
            {"language": "Hindi", "fluency": "professional"},
        ],
        "easy_apply_answers": {
            "authorization_to_work": {"India": True, "IN": True, "US": False},
            "sponsorship_needed": False,
            "salary_expectations_min": 2500000,
            "salary_expectations_max": 3500000,
            "salary_currency": "INR",
            "notice_period": "30 days",
            "start_date_available": "30 days",
            "current_location": "Bengaluru, Karnataka, India",
            "willing_to_relocate": False,
            "work_preference": "flexible",
            "highest_education_level": "Bachelor's",
        },
    }


def get_mock_master_knowledge_bank() -> dict:
    return {
        "version": "1.0.0",
        "candidate_name": "Test Candidate",
        "target_roles": [
            "Senior SDET",
            "Lead SDET",
            "Test Automation Architect",
            "Senior QA Automation Engineer",
        ],
        "master_achievements_vault": [
            {
                "domain": "API & UI Automation Architecture",
                "company": "Value Labs",
                "star_achievement": "Mosaic Order Automation Framework: Architected UI and API automation frameworks for 6+ airline projects leveraging REST Assured, Selenium, and BDD; built 1500+ test cases, reducing execution effort from 1,125 to 125 man-hours (90% reduction). Integrated with Harness CI/CD pipelines to run and monitor daily and weekly runs for smoke and regression suites.",
                "tools": ["REST Assured", "Selenium", "BDD", "Harness", "Java"],
                "metric": "90% regression execution effort reduction (1,125 to 125 man-hours)",
            },
            {
                "domain": "Observability & Automated Defect Detection",
                "company": "Value Labs",
                "star_achievement": "Log Monitoring & Tooling: Automated daily error log analysis in Kibana for 30+ microservices for 6+ projects leveraging AI for implementation, detecting 2-4 critical bugs prior to each release. Built internal productivity tools integrating Azure DevOps APIs and release dashboards to track effort and team compliance.",
                "tools": ["Kibana", "Azure DevOps", "Agentic AI", "Python", "REST API"],
                "metric": "Detected 2-4 critical bugs prior to each release across 30+ microservices",
            },
            {
                "domain": "AI-Assisted Quality Engineering",
                "company": "Value Labs",
                "star_achievement": "AI Initiatives: Designed Agents using Copilot which leveraged AI to automate STLC processes with Azure DevOps, Maven Integration allowing the team to fast track STLC further reducing delivery time by 60%.",
                "tools": ["Copilot", "Agentic AI", "Azure DevOps", "Maven", "Java"],
                "metric": "60% delivery time reduction via STLC automation",
            },
            {
                "domain": "Ekam Microservices Framework",
                "company": "Dunzo",
                "star_achievement": "Automated end-to-end API flows and DB validations using the Ekam Java Framework for 4 key features, achieving 60% test coverage in a microservices-based Merchant Service suite.",
                "tools": ["Java", "Ekam Framework", "PostgreSQL", "REST API"],
                "metric": "60% test coverage in Merchant Service suite",
            },
            {
                "domain": "Cloud Stability & Root Cause Analysis",
                "company": "Dunzo",
                "star_achievement": "Designed and maintained resilient regression suites using Postman, Newman, and Jenkins, enabling continuous daily validation for critical payment and order flows.",
                "tools": ["Postman", "Newman", "Jenkins", "CI/CD"],
                "metric": "Zero payment regression escapes via continuous daily automated runs",
            },
            {
                "domain": "SDLC Quality Governance",
                "company": "Dunzo",
                "star_achievement": "Streamlined QA release sign-offs by collaborating in Agile sprints, performing rigorous root-cause analysis, and logging actionable defects in Jira.",
                "tools": ["Jira", "Agile", "Root Cause Analysis"],
                "metric": "100% on-time sprint sign-offs with zero production blocker escapes",
            },
            {
                "domain": "Mobile & UI Automation Framework",
                "company": "Tata Elxsi",
                "star_achievement": "Falcon OTT Test Automation: Engineered automated test suites in Python, Appium, and PyTest for a multi-platform OTT application, improving test efficiency by 40% across Web, Android, iOS, and Smart TVs.",
                "tools": ["Python", "PyTest", "Selenium", "Appium"],
                "metric": "40% test efficiency improvement across 4 platforms",
            },
            {
                "domain": "Consumer App Quality & Store Rating",
                "company": "Tata Elxsi",
                "star_achievement": "CI/CD Integration: Configured Git and Jenkins pipelines for automated test execution, eliminating 15 hours of manual testing effort per sprint release.",
                "tools": ["Jenkins", "Git", "CI/CD"],
                "metric": "Eliminated 15 hours of manual testing per sprint release",
            },
            {
                "domain": "Domain API & KPI Testing",
                "company": "Tata Elxsi",
                "star_achievement": "Defect Lifecycle Management: Authored 300+ comprehensive test scenarios, tracked defects in Bugzilla, and conducted cross-functional defect triage with development and product leads.",
                "tools": ["Bugzilla", "Jira", "Test Planning"],
                "metric": "Authored 300+ test scenarios across multi-platform video playback matrices",
            },
            {
                "domain": "AI Automation & Process Engineering",
                "company": "Value Labs / Tooling",
                "star_achievement": "Engineered automated test harness tools integrating Azure DevOps REST APIs and real-time sprint metric dashboards.",
                "tools": ["Python", "REST API", "Azure DevOps"],
                "metric": "Real-time sprint QA metric visibility",
            },
            {
                "domain": "API Automation & Defect Management",
                "company": "Value Labs / Tooling",
                "star_achievement": "Developed automated defect categorization scripts to accelerate bug triage in continuous regression runs.",
                "tools": ["Python", "Jira", "Automation"],
                "metric": "Accelerated bug triage cycles",
            },
            {
                "domain": "Modern Test Architecture & Parallel Execution",
                "company": "Technical Projects",
                "star_achievement": "Architected end-to-end parallel test execution suites utilizing Playwright and TypeScript with distributed CI worker sharding.",
                "tools": ["Playwright", "TypeScript", "CI/CD"],
                "metric": "70% regression execution speedup",
            },
            {
                "domain": "API Contract Testing & Service Virtualization",
                "company": "Technical Projects",
                "star_achievement": "Integrated consumer-driven contract testing and service virtualization leveraging Pact and WireMock across microservices.",
                "tools": ["Pact", "WireMock", "REST API"],
                "metric": "Zero contract drift across microservice boundaries",
            },
            {
                "domain": "Event-Driven Stream Validation",
                "company": "Technical Projects",
                "star_achievement": "Engineered asynchronous message queue validation suites leveraging Kafka and Python to ensure schema integrity and sub-second event latency.",
                "tools": ["Kafka", "Python", "Microservices"],
                "metric": "Sub-second event latency and schema validation",
            },
            {
                "domain": "Cloud Native Ephemeral Environments",
                "company": "Technical Projects",
                "star_achievement": "Containerized ephemeral test runners using Docker and Kubernetes across GitHub Actions CI workflows.",
                "tools": ["Docker", "Kubernetes", "CI/CD", "GitHub Actions"],
                "metric": "75% faster feedback cycles via ephemeral containerized test runners",
            },
        ],
    }


def deploy_mock_fixtures_if_missing():
    """
    Deploys programmatic zero-secret mock fixtures into gitignored data/
    directories if real candidate files are not present.
    """
    data_dir = os.path.join(PROJECT_ROOT, "data")
    profile_dir = os.path.join(data_dir, "profile")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)

    # 1. candidate_master_data.json
    target_cmd = os.path.join(profile_dir, "candidate_master_data.json")
    if not os.path.exists(target_cmd):
        with open(target_cmd, "w", encoding="utf-8") as f:
            json.dump(get_mock_candidate_master_data(), f, indent=2)
        print("   ℹ️ Initialized programmatic mock data/profile/candidate_master_data.json")

    # 2. resume_profile.json
    target_profile = os.path.join(data_dir, "resume_profile.json")
    if not os.path.exists(target_profile):
        with open(target_profile, "w", encoding="utf-8") as f:
            json.dump(get_mock_resume_profile(), f, indent=2)
        print("   ℹ️ Initialized programmatic mock data/resume_profile.json")

    # 3. master_knowledge_bank.json
    target_kb = os.path.join(data_dir, "master_knowledge_bank.json")
    if not os.path.exists(target_kb):
        with open(target_kb, "w", encoding="utf-8") as f:
            json.dump(get_mock_master_knowledge_bank(), f, indent=2)
        print("   ℹ️ Initialized programmatic mock data/master_knowledge_bank.json")

    # 4. application_history.json
    target_hist = os.path.join(data_dir, "application_history.json")
    if not os.path.exists(target_hist):
        with open(target_hist, "w", encoding="utf-8") as f:
            f.write("[]\n")
        print("   ℹ️ Initialized baseline data/application_history.json")

    # 5. processed_jobs.json
    target_proc = os.path.join(data_dir, "processed_jobs.json")
    if not os.path.exists(target_proc):
        with open(target_proc, "w", encoding="utf-8") as f:
            f.write("{}\n")
        print("   ℹ️ Initialized baseline data/processed_jobs.json")
