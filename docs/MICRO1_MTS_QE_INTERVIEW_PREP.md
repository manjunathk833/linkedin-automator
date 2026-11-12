# micro1 AI Interview ("Zara") — Fast-Track Master Prep Guide
**Role:** Member of Technical Staff, Quality Engineering (Core Team — $260K–$400K/yr)  
**Candidate:** Manjunath H K (`6.8 YOE` / `7 Years` | Senior SDET & AI-Augmented Quality Architect)  
**Interview Format:** ~23-Minute Conversational AI Interview (Zara) + ~15–20 Minute Live Screen-Shared Coding Exercise  
**Hard Deadline:** **November 10, 2026 at 05:14 PM IST** (48-hour expiry)

---

## 1. How Zara Scores You & Anti-Cheat Survival Rules

micro1's AI interviewer (**Zara**) is a real-time GPT-4o voice-to-voice system combined with strict browser proctoring and a live coding runner.

### 1.1 The 4 Exact Graded Focus Areas (Configured on Your Requisition)
Zara allocates **~5.5 to 6 minutes per skill block** across these 4 exact pillars:
1. **Test Automation Engineering & Framework Architecture**
2. **AI Agents & Agentic QA Automation**
3. **Quality Engineering Systems & CI/CD Integration**
4. **Technical Leadership & Quality Engineering Strategy**

### 1.2 Critical Proctoring & Delivery Rules
1. **The `< 2.5 Second` Response Latency Rule (Crucial):**
   - Zara's anti-cheat layer tracks the exact pause between the end of her sentence and the start of your voice.
   - **Never pause silently for 5–8 seconds.** Start speaking within **1.5–2 seconds** using a **Bridge Phrase** while organizing your thoughts:
     - *"That's a core architectural problem we solved at ValueLabs — I break that down into three layers: first..."*
     - *"In a high-velocity microservices environment, I approach this across three dimensions: determinism, observability, and CI gating..."*
2. **The 90–120 Second Rule (`Headline -> 3 Technical Pillars -> Metric`):**
   - Keep every spoken answer between **90 and 120 seconds**.
   - Structure every response clearly with signposts (*"First... Second... Third... As a result..."*) — LLM graders score structured, numbered reasoning significantly higher than stream-of-consciousness answers.
3. **Adaptive Drill-Down Rule (No Unbacked Buzzwords):**
   - Zara dynamically generates follow-up questions from the exact nouns you speak and from your uploaded resume (`Manjunath_HK_Joblet_AI_44876342_Resume.pdf`).
   - Only name tools and metrics you can immediately explain under the hood (`Mosaic`, `REST Assured`, `Selenium`, `Playwright`, `Docker`, `Harness`, `Jenkins`, `Kafka`, `Kibana`, `Dynatrace`, `PostgreSQL`, `GitHub Copilot`, `Ollama`, `Claude/Gemini APIs`).
4. **Screen Share, Gaze & Browser Hygiene:**
   - Share your **Entire Screen** when prompted (not just a single tab).
   - Close all secondary monitors, notifications, Slack/WhatsApp popups, and background tabs before starting.
   - Look directly into the webcam/screen center. If Chrome ever stalls on the audio widget, micro1's engineering community recommends keeping **Firefox** installed as an instant backup browser.

---

## 2. Free Online Coding Tools (Zero-Login, Instant Browser Practice)

Use these free browser IDEs right now to warm up for the 15–20 minute coding exercise:

| Tool | Best For | Direct Practice URL |
| :--- | :--- | :--- |
| **1. micro1 Official Mock Interview** | Testing your microphone, webcam, and Zara's voice cadence before starting the real link | https://www.micro1.ai/interview-prep |
| **2. LeetCode Playground (Monaco IDE)** | **Exact match** for micro1's browser Monaco editor; run Python 3 & Java code with custom `stdin` | https://leetcode.com/playground/new/empty |
| **3. Programiz Python Compiler** | Zero-login, fast 1-click execution for practicing the 8 Python coding drills in Section 5 | https://www.programiz.com/python-programming/online-compiler/ |
| **4. OneCompiler (Python & Java)** | Side-by-side multi-language runner with instant `stdout` verification | https://onecompiler.com/python |
| **5. NeetCode 150 Free Practice** | Interactive test-case runner for Arrays, HashMaps, Sliding Window, Stacks, and Graphs | https://neetcode.io/practice |

> **Recommendation for the Live Coding Exercise:** Choose **Python 3** (unless forced into Java). In micro1's browser IDE, Python requires zero class-wrapper boilerplate, handles JSON/strings/dicts in 1/3rd the lines of code, and lets you narrate your logic clearly while finishing with 5+ minutes to spare.

---

## 3. Verbal Questions by Increasing Difficulty (With Spoken Model Answers)

Each question below is mapped to your 4 focus areas and moves from **Level 1 (Foundation)** $\rightarrow$ **Level 2 (Intermediate)** $\rightarrow$ **Level 3 (Advanced Distributed Systems)** $\rightarrow$ **Level 4 (Staff / Architect & Agentic AI)**.

---

### LEVEL 1: Foundation (Core QA, API & UI Automation Principles)

#### Q1. [Framework Architecture] How do you decide what to automate at the UI layer versus the API or integration layer?
> **Spoken Answer (90s):**
> "I enforce a strict inverted-pyramid strategy grounded in execution cost, determinism, and blast radius.
> **First, at the API and contract layer (roughly 70% of automated coverage):** Any business rule, state transition, payload schema validation, auth boundary, or database side-effect belongs at the API layer using REST Assured or Python `pytest`. API tests run in milliseconds, don't suffer from DOM rendering jitter, and pinpoint exact microservice failures.
> **Second, at the integration and event layer (~20%):** For asynchronous workflows—like Kafka event consumers or PostgreSQL state updates that I tested at Dunzo and ValueLabs—we validate message serialization, idempotency, and eventual consistency directly against service endpoints and DB state.
> **Third, at the UI layer (~10%):** I restrict Selenium and Playwright UI tests strictly to revenue-critical user journeys—such as booking checkout flows across our 6+ airline programs—where browser rendering, session state, and cross-component integration must be verified end-to-end.
> **Impact:** By shifting assertion density down into REST Assured and keeping UI suites lean and modular, we scaled to 1,500+ automated tests at ValueLabs while cutting total regression effort by 90%, from 1,125 man-hours down to 125 man-hours."

#### Q2. [Framework Architecture] How do you structure a scalable UI and API automation framework from scratch?
> **Spoken Answer (90s):**
> "When I architected the **Mosaic** automation framework at ValueLabs across 6+ airline programs, I separated the architecture into four decoupled layers so test authors never write raw HTTP or WebDriver calls inside test classes:
> **Layer 1 is the Core Driver & Client Engine:** Thread-safe `ThreadLocal` WebDriver/Playwright context management and reusable REST Assured specification builders with centralized auth-token refresh, retry interceptors, and request/response logging filters.
> **Layer 2 is the Domain Abstraction Layer:** For UI, we use strict Page Object and Component Object models where locators and wait conditions are encapsulated. For APIs, we use typed POJO/Pydantic request-response models and builders.
> **Layer 3 is the Business Workflow / BDD Layer:** Clean Cucumber BDD steps or fluent service orchestrators that compose multi-step business actions—like searching a flight, holding inventory, and verifying payment status.
> **Layer 4 is Execution, Observability & Reporting:** Dockerized test runners integrated into Harness and Jenkins CI/CD, publishing telemetry to Allure and feeding failure payloads into our AI defect-triage pipeline."

#### Q3. [CI/CD & Quality Systems] What is the difference between verification of synchronous REST APIs versus asynchronous event-driven microservices?
> **Spoken Answer (90s):**
> "Synchronous REST testing is request-response deterministic: you send an HTTP payload, assert the status code, validate the JSON schema, and verify the synchronous database write.
> Asynchronous event-driven testing—such as the 30+ Kafka-backed microservices I test at ValueLabs—requires handling **eventual consistency, out-of-order delivery, and idempotency**:
> **First**, instead of `Thread.sleep`, we use bounded polling assertions (such as Awaitility) with strict SLA timeouts to poll downstream state or Kafka consumer offsets.
> **Second**, we test **idempotency** by replaying the exact same event message ID twice and asserting that downstream PostgreSQL state and side effects occur exactly once.
> **Third**, we correlate distributed traces using `correlation_id` headers across Kibana and Dynatrace logs so if a consumer drops or dead-letters a message, our test fails with the exact service hop and stack trace."

---

### LEVEL 2: Intermediate (Framework Engineering, Flakiness & CI/CD Gates)

#### Q4. [CI/CD & Quality Systems] How do you diagnose, quarantine, and eliminate flaky tests in a large CI/CD suite?
> **Spoken Answer (105s):**
> "Flakiness destroys developer trust in CI gates. If a suite has even a 3% random failure rate across 1,500 tests, every PR build turns red. I treat flakiness as a first-class engineering metric using a four-step loop:
> **First, Automated Detection & Quarantine:** We track pass-after-retry rates across CI runs. Any test that flips state on the same commit hash without a production defect is automatically tagged `@Quarantine` and moved out of the blocking PR merge gate into a non-blocking quarantine suite with an auto-filed ticket.
> **Second, Root-Cause Classification:** In my experience, 85% of flakes come from three sources:
> 1. *Async timing & DOM hydration races* — which we fix by replacing static waits with explicit network-idle or DOM-state predicates.
> 2. *Shared mutable test data collisions* — when parallel workers mutate the same user account or flight inventory, which we fix via isolated per-worker test data seeding and unique UUID namespaces.
> 3. *Third-party environment instability* — which we isolate at the PR stage via deterministic service mocks/stubs while keeping live integration checks in scheduled staging monitors.
> **Third, Re-admission Gate:** A quarantined test must pass **20 consecutive parallel executions** in CI before graduating back into the blocking regression gate."

#### Q5. [Framework Architecture] How do you design parallel execution and test data isolation so 1,500+ tests run reliably inside Dockerized CI/CD pipelines?
> **Spoken Answer (100s):**
> "Running 1,500+ tests in parallel requires strict isolation at both the **process memory level** and the **stateful backend level**:
> **First, Thread & Context Isolation:** In Java/TestNG and Cucumber, every worker thread gets its own isolated `ThreadLocal` WebDriver/Playwright browser context and independent REST Assured request specification—zero static mutable singletons.
> **Second, Dynamic Test Data Isolation:** Parallel tests fail when Test A deletes or modifies a record that Test B is reading. At Dunzo on the Merchant Service and at ValueLabs on airline booking flows, we implemented **API-first state seeding**: each test provisions its own isolated entity (merchant/user/booking) via fast setup APIs before the test starts and cleans up via teardown hooks or isolated DB schemas.
> **Third, Containerized Sharding in Harness & Jenkins:** We package the test runner and browser grid into Docker containers and shard suites by execution-time weight across parallel CI nodes, cutting wall-clock feedback time so full regression completes within our daily/weekly CI windows."

#### Q6. [AI Agents & Agentic QA] You built an AI-driven Azure DevOps defect pipeline that auto-files bugs when confidence exceeds 95%. Walk me through exactly how it works under the hood.
> **Spoken Answer (115s):**
> "At ValueLabs, engineers were spending hours every morning triaging regression failures across 6+ airline programs and manually cross-referencing user stories in Azure DevOps. I built an automated AI triage and defect-filing pipeline integrated directly into our REST Assured and UI test listeners:
> **Step 1 — Failure Context Harvesting:** When a test fails in Harness CI, the failure listener captures a structured diagnostic bundle: the assertion diff, HTTP request/response payload (with PII scrubbed), stack trace, and matching Kibana/Dynatrace error logs via correlation ID.
> **Step 2 — Requirement Retrieval & Deduplication:** The pipeline queries the Azure DevOps REST API to fetch the linked User Story acceptance criteria and searches existing open defects in the current sprint to prevent duplicate bug creation.
> **Step 3 — Structured LLM Evaluation & Confidence Scoring:** We pass the failure bundle and user story acceptance criteria to the LLM with a strict JSON schema prompt. The model classifies whether the failure is an *Application Bug*, *Environment/5xx Outage*, or *Test/Selector Issue*, and outputs a calibrated confidence score based on evidence alignment (e.g., an explicit HTTP 500 or schema mismatch against acceptance criteria scores `>95%`).
> **Step 4 — Deterministic Gate:** Only when the classification is `Application Bug`, no duplicate open defect exists, and confidence exceeds `95%`, the agent automatically creates the Azure DevOps Bug work item populated with reproduction steps, environment metadata, and log snippets—cutting manual triage and bug-filing effort by **70%**."

---

### LEVEL 3: Advanced (Distributed Observability, AI Agents & STLC Automation)

#### Q7. [AI Agents & Agentic QA] Your resume mentions designing Copilot-based AI agents automating STLC workflows that cut delivery time by 60%. How did you architect those agents?
> **Spoken Answer (115s):**
> "Our goal was to scale test creation and maintenance across 6+ airline programs without scaling QA headcount linearly with product complexity. I designed a multi-stage Agentic STLC workflow around Azure DevOps, Maven, and LLM APIs:
> **Stage 1 — Requirement-to-Scenario Agent:** Triggered when a User Story moves to *Ready for QA* in Azure DevOps, the agent parses the acceptance criteria and OpenAPI/Swagger spec changes, generating structured positive, negative, and boundary Gherkin scenarios for human review.
> **Stage 2 — Context-Grounded Code Synthesis:** Instead of letting an LLM hallucinate arbitrary code, we index our existing **Mosaic** framework's Page Objects, REST Assured client helpers, and utility methods. The agent synthesizes step definitions and API test classes that strictly reuse existing framework abstractions.
> **Stage 3 — Self-Verification Loop (`mvn test-compile`):** Before opening a PR or presenting the code, the agent runs a local Maven compile and dry-run check. If there is a missing import or type mismatch, the compiler error is fed back to the agent to self-correct.
> **Result:** Engineers review a clean, compiling PR rather than writing boilerplate from scratch—reducing end-to-end test delivery time by **60%** while keeping framework standards 100% uniform."

#### Q8. [Quality Systems & Observability] How do you use Kibana, Dynatrace, and Kafka event logs for proactive quality engineering rather than just post-mortem debugging?
> **Spoken Answer (105s):**
> "Passing functional assertions in CI isn't enough if a microservice is silently throwing retry storms, memory spikes, or dead-letter queue errors under the hood.
> At ValueLabs across 30+ airline microservices—and previously at Dunzo using GCP Metrics Explorer, Kibana, and Kubernetes—I built **automated daily observability health gates**:
> **First, Log & Exception Fingerprinting:** We automated queries against Kibana and Dynatrace APIs to scan for new `5xx` spikes, unhandled null-pointer exceptions, slow SQL queries, and latency p95 regressions introduced after each deployment.
> **Second, Kafka Event-Log Integrity:** We monitor consumer lag and Dead Letter Topics (DLTs) during automated regression runs to catch schema serialization mismatches or poison-pill messages that didn't immediately break the UI response.
> **Impact:** This shift-right observability automation consistently catches **2 to 4 critical release-blocking defects before every production release** that traditional pass/fail UI tests would have missed."

---

### LEVEL 4: Staff / Architect & Agentic QA Systems (Specifically for micro1 MTS Role)

#### Q9. [AI Agents & Agentic QA] How would you architect an autonomous Agentic QA system that generates tests, executes regression, investigates failures, and self-heals—without scaling QA headcount?
> **Spoken Answer (120s — Memorize This Core Architecture):**
> "To build an autonomous quality system at Staff level, I design a **closed-loop 4-Agent Architecture with deterministic guardrails**:
> **1. Change-Impact & Planner Agent (Trigger Layer):** On every PR or API spec diff, this agent analyzes the AST/code diff and dependency graph to identify the exact blast radius—selecting which existing tests to run and identifying coverage gaps that need new test cases.
> **2. Test Generation & Execution Agent (Builder Layer):** Grounded in a live index of the repository's existing fixtures and API clients, it generates new unit, API, or E2E Playwright tests, executes them in an isolated ephemeral Docker sandbox, and verifies that the new test passes against the feature branch and fails against the mutated condition.
> **3. Failure Investigator & Triage Agent (Diagnostic Layer):** When a regression test fails, this agent correlates the DOM snapshot, HAR network trace, and backend microservice logs. It classifies the root cause into three buckets:
>    - *Bucket A: Selector/UI refactor* $\rightarrow$ routes to the **Self-Healing Agent** to patch the locator and open an auto-PR.
>    - *Bucket B: Real product regression* $\rightarrow$ auto-files a high-confidence defect with exact commit blame and reproduction artifacts.
>    - *Bucket C: Transient infra/network flake* $\rightarrow$ triggers an isolated retry and logs telemetry.
> **4. Human-in-the-Loop Governance Gate:** No agent merges code or mutates production test baselines without passing deterministic linting, compilation, and confidence thresholds (`>95%`). This lets a small Staff QE team govern quality across dozens of product engineers."

#### Q10. [AI Agents & Agentic QA] How do you test and evaluate non-deterministic AI / LLM systems and agents where the same input can produce different valid outputs?
> **Spoken Answer (115s):**
> "Testing LLM and agentic workflows requires moving from exact string matching (`assertEqual`) to a **3-Tier Evaluation Pyramid**:
> **Tier 1 — Deterministic Structural & Tool-Call Assertions (Fastest, Every PR):** Even when text is probabilistic, tool invocations, JSON output schemas, SQL queries, API parameters, and security guardrails must be 100% deterministic. We validate JSON schemas, assert that the agent called the expected tool sequence with valid arguments, and mock LLM responses to test downstream error-handling deterministically.
> **Tier 2 — Golden Dataset & Semantic / Rubric Evaluation (LLM-as-a-Judge):** We maintain a versioned Golden Dataset of representative inputs, edge cases, and adversarial prompts. We evaluate outputs across four metrics: **Faithfulness / Hallucination rate** (is the output grounded strictly in retrieved context?), **Answer Relevance**, **Instruction Adherence**, and **Latency/Token budget**. To make LLM-as-a-Judge reliable, we use binary/integer rubric scoring (`0` or `1` per criterion) at `temperature=0` rather than vague 1–10 scales.
> **Tier 3 — Production Shadow & Drift Monitoring:** We sample live agent traces to detect prompt drift, latency spikes, or multi-turn looping, and automatically promote failed production traces into the Golden Regression Dataset."

#### Q11. [Technical Leadership & Strategy] You join as the founding Staff Quality Engineer on a fast-shipping engineering team with low test coverage and frequent regressions. What is your 30-60-90 day technical strategy?
> **Spoken Answer (110s):**
> "My strategy is to deliver immediate risk reduction in 30 days while building self-sustaining engineering leverage by day 90:
> **First 30 Days — Stabilize the Bleeding & Establish CI Truth:**
> I audit production incident post-mortems from the last 60 days to identify the top 10 revenue- and reliability-critical paths. I build a fast, zero-flake smoke/critical-path gate (`<10 minutes` execution time) wired directly into PR checks, and quarantine any noisy legacy tests so a red build always means a real bug.
> **Days 31 to 60 — Shift-Left Developer Enablement & API/Contract Layer:**
> Rather than QA becoming a manual bottleneck at the end of the sprint, I embed reusable test harnesses, ephemeral Docker environments, and PR-level API/integration templates so product engineers can write and run tests locally in one command.
> **Days 61 to 90 — Agentic Automation & Observability Loop:**
> I roll out agentic test generation for new PRs, automated failure triage (like my 95%-confidence defect pipeline), and pre-release log/trace observability gates—tracking **Change Failure Rate**, **Mean Time to Detect (MTTD)**, and **Defect Escape Rate** as our north-star metrics."

#### Q12. [Technical Leadership & Strategy] How do you drive quality ownership across product developers who view writing tests as "QA's job"?
> **Spoken Answer (95s):**
> "Developers resist testing when test frameworks are slow, flaky, or painful to run locally. As a Staff QE leader, I treat the engineering team as my internal customers and remove friction in three ways:
> **First, Paved-Road Tooling:** I build clean builders, fixtures, and AI/Copilot test-generation agents so writing an API or integration test takes 3 minutes instead of 45 minutes.
> **Second, Fast PR Feedback (`<10 min` SLA):** I split suites into a fast, deterministic Tier-1 PR gate that runs in under 10 minutes and a deeper Tier-2 nightly/pre-release regression suite.
> **Third, Shared Quality Governance in Code Reviews & Post-Mortems:** As I did leading code reviews across a 10+ member team at ValueLabs, we make test coverage and observability assertions part of the PR Definition of Done, backed by transparent service-level quality scorecards."

---

## 4. Resume Deep-Dive Follow-Up Traps (What Zara Will Ask Next)

When you mention your achievements from `ValueLabs` or `Dunzo`, expect Zara to ask one of these immediate 2nd-level follow-up probes:

| Your Resume Claim | Zara's Likely Follow-Up Probe | Your 45-Second Crisp Answer |
| :--- | :--- | :--- |
| **"Reduced regression effort by 90% (from 1,125 to 125 man-hours) across 6+ airline programs"** | *"How did one framework support 6+ different airline programs without becoming a tangled mess of `if/else` statements?"* | "We used a **Core + Tenant Configuration Architecture** in Mosaic. Core airline domain workflows (search, PNR creation, seat selection, payment) were defined against shared interfaces, while airline-specific endpoints, payload schemas, and feature flags were injected via tenant configuration profiles at runtime in Harness CI." |
| **"95% confidence threshold for AI defect auto-filing"** | *"What happens when the confidence score is below 95%? And how did you prevent false positives during staging outages?"* | "First, if multiple tests fail simultaneously with HTTP 502/503/504 or connection timeouts, a **circuit-breaker rule** flags an environment outage and suppresses individual bug filing. Second, any failure scoring between 60% and 94% is routed to a human review queue in our daily triage report with the pre-drafted summary attached—so zero real bugs are lost and zero noisy tickets pollute Azure DevOps." |
| **"Automated API flows and PostgreSQL validations using Ekam at Dunzo (60% coverage)"** | *"Why did you validate PostgreSQL directly in addition to checking the API response?"* | "In our Merchant Service microservices, an API could return `200 OK` while an asynchronous worker or transaction rollback left inconsistent state in PostgreSQL. By querying PostgreSQL directly inside the test transaction boundary—and testing pod/DB failure recovery on Kubernetes (`kubectl`)—we caught silent data-corruption bugs before production." |

---

## 5. Live Coding Exercise Drills (Increasing Difficulty: Easy $\rightarrow$ Medium $\rightarrow$ Hard)

> **How to Execute in the Live Coding Section:**
> 1. **First 60 seconds:** Read the problem out loud, state the input/output types, and state the time & space complexity target before typing (e.g., *"I'll use a HashMap and a sliding window to solve this in $O(N)$ time and $O(K)$ space"*).
> 2. **While coding:** Narrate every block as you type—Zara's audio transcript remains active during coding!
> 3. **Last 2 minutes:** Walk through 1 normal test case and 2 edge cases (`empty input`, `single element / boundary timestamp`) before clicking Submit.

---

### DRILL 1 (Easy — Warm-Up): Automated Test Run Log Aggregator
**Practice Live on:** [Programiz Python IDE](https://www.programiz.com/python-programming/online-compiler/) or [LeetCode Playground](https://leetcode.com/playground/new/empty)

**Problem Statement:**  
Given a list of test execution log strings in the format `"<timestamp>|<suite_name>|<test_id>|<status>"` where `status` is `"PASS"`, `"FAIL"`, or `"SKIP"`, return a list of `suite_name`s whose failure rate (`FAIL / (PASS + FAIL)`) is strictly greater than a given `threshold` (e.g. `0.20`), sorted by failure rate descending (and alphabetically by `suite_name` on ties). Ignore `"SKIP"` runs and ignore duplicate retries of the same `(suite_name, test_id)` by keeping only the **latest** timestamped result.

#### Python 3 Solution ($O(N \log N)$ Time, $O(N)$ Space)
```python
from collections import defaultdict
from typing import List


def find_unhealthy_suites(logs: List[str], threshold: float) -> List[str]:
    # 1. Deduplicate by (suite_name, test_id), keeping the latest timestamp
    latest_run = {}  # (suite, test_id) -> (timestamp, status)
    for entry in logs:
        if not entry or "|" not in entry:
            continue
        ts_str, suite, test_id, status = entry.strip().split("|")
        ts = int(ts_str)
        key = (suite, test_id)
        if key not in latest_run or ts >= latest_run[key][0]:
            latest_run[key] = (ts, status)

    # 2. Aggregate PASS and FAIL counts per suite (ignoring SKIP)
    totals = defaultdict(int)
    fails = defaultdict(int)
    for (suite, _), (_, status) in latest_run.items():
        if status == "SKIP":
            continue
        totals[suite] += 1
        if status == "FAIL":
            fails[suite] += 1

    # 3. Filter by failure rate > threshold and sort (-rate, suite_name)
    flagged = []
    for suite, total in totals.items():
        if total > 0:
            rate = fails[suite] / total
            if rate > threshold:
                flagged.append((suite, rate))

    flagged.sort(key=lambda x: (-round(x[1], 6), x[0]))
    return [suite for suite, _ in flagged]


if __name__ == "__main__":
    sample_logs = [
        "100|CheckoutSuite|T1|FAIL",
        "105|CheckoutSuite|T1|PASS",  # Retry passed -> overrides T1 FAIL
        "102|CheckoutSuite|T2|FAIL",
        "103|AuthSuite|T1|FAIL",
        "104|AuthSuite|T2|PASS",
        "106|SearchSuite|T1|SKIP",
    ]
    # CheckoutSuite: T1=PASS, T2=FAIL -> 1/2 = 0.50
    # AuthSuite: T1=FAIL, T2=PASS -> 1/2 = 0.50
    print(find_unhealthy_suites(sample_logs, 0.25))  # ['AuthSuite', 'CheckoutSuite']
```

#### Java Solution
```java
import java.util.*;

public class Solution {
    static class RunRecord {
        long timestamp;
        String status;
        RunRecord(long timestamp, String status) {
            this.timestamp = timestamp;
            this.status = status;
        }
    }

    public static List<String> findUnhealthySuites(List<String> logs, double threshold) {
        Map<String, RunRecord> latestRun = new HashMap<>();
        for (String log : logs) {
            if (log == null || !log.contains("|")) continue;
            String[] parts = log.trim().split("\\|");
            long ts = Long.parseLong(parts[0]);
            String key = parts[1] + "#" + parts[2];
            String status = parts[3];
            if (!latestRun.containsKey(key) || ts >= latestRun.get(key).timestamp) {
                latestRun.put(key, new RunRecord(ts, status));
            }
        }

        Map<String, int[]> counts = new HashMap<>(); // suite -> [fails, total]
        for (Map.Entry<String, RunRecord> e : latestRun.entrySet()) {
            String status = e.getValue().status;
            if ("SKIP".equals(status)) continue;
            String suite = e.getKey().split("#")[0];
            counts.putIfAbsent(suite, new int[]{0, 0});
            if ("FAIL".equals(status)) counts.get(suite)[0]++;
            counts.get(suite)[1]++;
        }

        List<String> result = new ArrayList<>();
        Map<String, Double> rates = new HashMap<>();
        for (Map.Entry<String, int[]> e : counts.entrySet()) {
            int f = e.getValue()[0], t = e.getValue()[1];
            if (t > 0) {
                double rate = (double) f / t;
                if (rate > threshold) {
                    result.add(e.getKey());
                    rates.put(e.getKey(), rate);
                }
            }
        }

        result.sort((a, b) -> {
            int cmp = Double.compare(rates.get(b), rates.get(a));
            return cmp != 0 ? cmp : a.compareTo(b);
        });
        return result;
    }
}
```

---

### DRILL 2 (Easy-Medium): Flaky Test Detector (State-Flip Analysis)
**Problem Statement:**  
A test is considered **flaky** on a given `commit_sha` if it exhibits **both** `"PASS"` and `"FAIL"` statuses across multiple executions on that **same** `commit_sha`. Given a list of execution records `(test_id, commit_sha, status)`, return all flaky `test_id`s sorted by the number of distinct commits on which they were flaky (descending), then by `test_id` ascending.

#### Python 3 Solution ($O(N)$ Time, $O(N)$ Space)
```python
from collections import defaultdict
from typing import List, Tuple


def detect_flaky_tests(runs: List[Tuple[str, str, str]]) -> List[str]:
    # Map (test_id, commit_sha) -> set of observed statuses
    commit_outcomes = defaultdict(set)
    for test_id, commit_sha, status in runs:
        if status in ("PASS", "FAIL"):
            commit_outcomes[(test_id, commit_sha)].add(status)

    # Count how many commits each test_id flipped state on
    flaky_commit_counts = defaultdict(int)
    for (test_id, _), statuses in commit_outcomes.items():
        if "PASS" in statuses and "FAIL" in statuses:
            flaky_commit_counts[test_id] += 1

    return [tid for tid, _ in sorted(flaky_commit_counts.items(), key=lambda item: (-item[1], item[0]))]


if __name__ == "__main__":
    data = [
        ("test_login", "c1", "FAIL"),
        ("test_login", "c1", "PASS"),
        ("test_login", "c2", "FAIL"),
        ("test_login", "c2", "PASS"),
        ("test_checkout", "c1", "FAIL"),
        ("test_checkout", "c1", "PASS"),
        ("test_payment", "c1", "FAIL"),
        ("test_payment", "c1", "FAIL"),  # Deterministic failure, NOT flaky
    ]
    print(detect_flaky_tests(data))  # ['test_login', 'test_checkout']
```

---

### DRILL 3 (Medium — Very Common on micro1): Sliding-Window API Rate Limiter / Circuit Breaker
**Problem Statement:**  
Implement a `SlidingWindowCircuitBreaker(window_seconds, max_failures)` class for an automated API test gateway.  
- `record_request(timestamp: int, is_success: bool) -> bool`: Records an API call at `timestamp` (in seconds, non-decreasing). If the number of failed requests (`is_success == False`) within the inclusive sliding window `[timestamp - window_seconds + 1, timestamp]` reaches or exceeds `max_failures`, the circuit trips and returns `False` (blocking the request); otherwise returns `True`.

#### Python 3 Solution ($O(1)$ Amortized per Call using `collections.deque`)
```python
from collections import deque


class SlidingWindowCircuitBreaker:
    def __init__(self, window_seconds: int, max_failures: int):
        self.window_seconds = window_seconds
        self.max_failures = max_failures
        self.failure_timestamps = deque()

    def record_request(self, timestamp: int, is_success: bool) -> bool:
        # 1. Evict failure timestamps outside [timestamp - window_seconds + 1, timestamp]
        cutoff = timestamp - self.window_seconds + 1
        while self.failure_timestamps and self.failure_timestamps[0] < cutoff:
            self.failure_timestamps.popleft()

        # 2. Record current failure if applicable
        if not is_success:
            self.failure_timestamps.append(timestamp)

        # 3. Check if circuit breaker threshold is breached
        return len(self.failure_timestamps) < self.max_failures


if __name__ == "__main__":
    cb = SlidingWindowCircuitBreaker(window_seconds=10, max_failures=3)
    print(cb.record_request(1, False))  # True (1 failure in [1..1])
    print(cb.record_request(4, False))  # True (2 failures in [1..4])
    print(cb.record_request(8, False))  # False (3 failures in [1..8] -> TRIPPED)
    print(cb.record_request(12, True))  # True (ts=1 expired; 2 failures [4,8] in [3..12])
```

---

### DRILL 4 (Medium): Recursive JSON Contract / Schema Validator
**Problem Statement:**  
Write a function `validate_payload(payload: dict, schema: dict) -> List[str]` that validates a nested API response dictionary against a schema dictionary and returns a sorted list of human-readable error strings (e.g. `"Missing key: user.id"`, `"Type mismatch at user.age: expected int, got str"`).
- Schema values can be a Python type (`int`, `str`, `bool`, `list`) or a nested `dict` representing a sub-object.

#### Python 3 Solution (Clean DFS with Dot-Path Tracking)
```python
from typing import Any, Dict, List

TYPE_MAP = {
    "int": int,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
}


def validate_payload(payload: Dict[str, Any], schema: Dict[str, Any], prefix: str = "") -> List[str]:
    errors: List[str] = []

    for key, expected in schema.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in payload:
            errors.append(f"Missing key: {path}")
            continue

        actual_val = payload[key]
        if isinstance(expected, dict):
            if not isinstance(actual_val, dict):
                errors.append(f"Type mismatch at {path}: expected dict, got {type(actual_val).__name__}")
            else:
                errors.extend(validate_payload(actual_val, expected, prefix=path))
        else:
            expected_type = TYPE_MAP.get(expected, expected)
            # Note: in Python bool is a subclass of int, so guard explicitly!
            if expected_type is int and isinstance(actual_val, bool):
                errors.append(f"Type mismatch at {path}: expected int, got bool")
            elif not isinstance(actual_val, expected_type):
                exp_name = expected if isinstance(expected, str) else expected_type.__name__
                errors.append(f"Type mismatch at {path}: expected {exp_name}, got {type(actual_val).__name__}")

    return sorted(errors)


if __name__ == "__main__":
    schema_def = {
        "status": "int",
        "user": {
            "id": "int",
            "email": "str",
            "active": "bool",
        },
    }
    bad_payload = {
        "status": 200,
        "user": {
            "id": True,  # Trap: bool is subclass of int in Python!
        },
    }
    print(validate_payload(bad_payload, schema_def))
    # ['Missing key: user.active', 'Missing key: user.email', 'Type mismatch at user.id: expected int, got bool']
```

---

### DRILL 5 (Medium-Hard): Test Suite Dependency Graph & Parallel Execution Waves (Kahn's Topological Sort)
**Problem Statement:**  
In a CI pipeline, certain integration tests depend on other setup/seed tests completing first. Given `tests: List[str]` and `dependencies: List[Tuple[str, str]]` where `(A, B)` means **test `A` must run before test `B`**, return the **minimum parallel execution waves** (`List[List[str]]`, with each wave sorted alphabetically) required to run all tests. If there is a circular dependency, return `[]`.

#### Python 3 Solution ($O(V + E)$ Topological Level-Order BFS)
```python
from collections import defaultdict
from typing import List, Tuple


def schedule_test_waves(tests: List[str], dependencies: List[Tuple[str, str]]) -> List[List[str]]:
    in_degree = {t: 0 for t in tests}
    graph = defaultdict(list)

    for prereq, dependent in dependencies:
        graph[prereq].append(dependent)
        in_degree[dependent] = in_degree.get(dependent, 0) + 1
        if prereq not in in_degree:
            in_degree[prereq] = 0

    current_wave = sorted([t for t, deg in in_degree.items() if deg == 0])
    waves: List[List[str]] = []
    visited_count = 0

    while current_wave:
        waves.append(current_wave)
        visited_count += len(current_wave)
        next_wave = []
        for node in current_wave:
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_wave.append(neighbor)
        current_wave = sorted(next_wave)

    return waves if visited_count == len(in_degree) else []


if __name__ == "__main__":
    all_tests = ["seed_db", "auth_token", "create_order", "pay_order", "verify_ledger"]
    deps = [
        ("seed_db", "auth_token"),
        ("auth_token", "create_order"),
        ("create_order", "pay_order"),
        ("create_order", "verify_ledger"),
    ]
    print(schedule_test_waves(all_tests, deps))
    # [['seed_db'], ['auth_token'], ['create_order'], ['pay_order', 'verify_ledger']]
```

---

### DRILL 6 (Hard — Staff Level): First Broken Commit Finder with Flaky Guard (Binary Search + Verification Quorum)
**Problem Statement:**  
You are building an automated `git bisect` triage agent for `N` commits `[0 .. N-1]`. Commit `0` is known good (`True`), and Commit `N-1` is broken (`False`). However, the test runner has up to a `20%` transient flake rate on failure. Write `find_first_bad_commit(n, run_test)` that minimizes commit checks while guaranteeing stability by running at most `k=3` majority/consensus checks per probed commit.

#### Python 3 Solution ($O(k \log N)$ Time)
```python
from typing import Callable


def is_commit_healthy(commit_idx: int, run_test: Callable[[int], bool], max_attempts: int = 3) -> bool:
    """Returns True if the commit passes at least once (since a passing run proves code isn't deterministically broken),
    or uses majority voting across max_attempts."""
    passes = 0
    fails = 0
    majority = (max_attempts // 2) + 1
    for _ in range(max_attempts):
        if run_test(commit_idx):
            passes += 1
            if passes >= majority:
                return True
        else:
            fails += 1
            if fails >= majority:
                return False
    return passes > fails


def find_first_bad_commit(n: int, run_test: Callable[[int], bool]) -> int:
    low, high = 0, n - 1
    first_bad = n - 1

    while low <= high:
        mid = (low + high) // 2
        if is_commit_healthy(mid, run_test):
            low = mid + 1
        else:
            first_bad = mid
            high = mid - 1

    return first_bad
```

---

## 6. 15-Minute Pre-Interview Launch Checklist

Before clicking **`Take the interview`** on `https://jobs.micro1.ai/post/success` (or your email link):
- [ ] **Run 1 Practice Prompt on [micro1 Interview Prep](https://www.micro1.ai/interview-prep)** to confirm microphone gain and camera framing.
- [ ] **Run Drill 1 & Drill 3 on [Programiz Python IDE](https://www.programiz.com/python-programming/online-compiler/)** (5 minutes) while speaking your logic out loud.
- [ ] **Close all other tabs, IDEs, Slack, and notification banners** so your full-screen share is 100% clean.
- [ ] **Keep your 4 Headline Metrics ready to cite naturally:**
  1. **Mosaic Framework (`ValueLabs`):** `1,500+` UI/API tests across `6+` airline programs $\rightarrow$ cut regression effort by **`90%`** (`1,125` $\rightarrow$ `125` man-hours).
  2. **AI Defect Pipeline (`ValueLabs`):** Azure DevOps + REST Assured auto-bug filing at **`>95%` confidence** $\rightarrow$ cut manual triage by **`70%`**.
  3. **Agentic STLC Automation (`ValueLabs`):** Copilot/LLM agents integrated with Azure DevOps & Maven $\rightarrow$ cut test delivery time by **`60%`** without scaling QA headcount.
  4. **Microservices Observability (`ValueLabs` & `Dunzo`):** Automated `Kibana`, `Dynatrace`, `Kafka`, and `PostgreSQL` checks across `30+` microservices $\rightarrow$ caught **`2–4` critical defects before every release**.
