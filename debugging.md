==================================================
  RUNNING RUFF AUTO-FIX LINTER & FORMATTER
==================================================

==================================================
  RUNNING RUFF LINTER & AUTO-FIX ENGINE
==================================================
🔧 Step 1: Auto-fixing linter errors & import order...
ASYNC230 Async functions should not open files with blocking methods like `open`
   --> main.py:111:18
    |
109 |     if os.path.exists(history_file):
110 |         try:
111 |             with open(history_file, "r") as f:
    |                  ^^^^
112 |                 history = json.load(f)
113 |         except Exception:
    |

BLE001 Do not catch blind exception: `Exception`
   --> main.py:113:16
    |
111 |             with open(history_file, "r") as f:
112 |                 history = json.load(f)
113 |         except Exception:
    |                ^^^^^^^^^
114 |             history = []
    |

ASYNC230 Async functions should not open files with blocking methods like `open`
   --> main.py:118:14
    |
116 |     for fname in json_files:
117 |         filepath = os.path.join(approved_dir, fname)
118 |         with open(filepath, "r") as f:
    |              ^^^^
119 |             payload = json.load(f)
    |

DTZ003 `datetime.datetime.utcnow()` used
   --> main.py:130:26
    |
128 |         # Log history entry
129 |         log_entry = {
130 |             "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    |                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
131 |             "job_id": job_id,
132 |             "company": company,
    |
help: Use `datetime.datetime.now(tz=...)` instead

ASYNC230 Async functions should not open files with blocking methods like `open`
   --> main.py:141:14
    |
140 |         # Write log back
141 |         with open(history_file, "w") as f:
    |              ^^^^
142 |             json.dump(history, f, indent=2)
    |

PLW1510 `subprocess.run` without explicit `check` argument
   --> main.py:158:5
    |
156 |     print("=" * 50 + "\n")
157 |     script = os.path.join(os.path.dirname(__file__), "verify", "autofix_lint.sh")
158 |     subprocess.run(["bash", script])
    |     ^^^^^^^^^^^^^^
help: Add explicit `check=False`

SIM118 Use `key in dict` instead of `key in dict.keys()`
  --> src/automation/easy_apply.py:69:21
   |
67 |                 yoe = profile.get_total_experience_years()
68 |                 # Check for specific skill match in label
69 |                 for skill_name in profile.skills_matrix.keys():
   |                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
70 |                     if skill_name.lower() in label_lower:
71 |                         yoe = profile.get_years_of_experience(skill_name)
   |
help: Remove `.keys()`

S110 `try`-`except`-`pass` detected, consider logging the exception
   --> src/automation/easy_apply.py:124:9
    |
122 |               if aria_label:
123 |                   return aria_label
124 | /         except Exception:
125 | |             pass
    | |________________^
126 |           return ""
    |

BLE001 Do not catch blind exception: `Exception`
   --> src/automation/easy_apply.py:124:16
    |
122 |             if aria_label:
123 |                 return aria_label
124 |         except Exception:
    |                ^^^^^^^^^
125 |             pass
126 |         return ""
    |

RUF059 Unpacked variable `context` is never used
   --> src/automation/easy_apply.py:156:17
    |
154 |             context = None
155 |             try:
156 |                 context, page = await launch_persistent_browser(p)
    |                 ^^^^^^^
157 |             except Exception as e1:
158 |                 print(f"⚠️ Persistent browser failed: {e1}, trying CDP fallback...")
    |
help: Prefix it with an underscore or any other dummy variable pattern

BLE001 Do not catch blind exception: `Exception`
   --> src/automation/easy_apply.py:157:20
    |
155 |             try:
156 |                 context, page = await launch_persistent_browser(p)
157 |             except Exception as e1:
    |                    ^^^^^^^^^
158 |                 print(f"⚠️ Persistent browser failed: {e1}, trying CDP fallback...")
159 |                 try:
    |

RUF059 Unpacked variable `browser` is never used
   --> src/automation/easy_apply.py:160:21
    |
158 |                 print(f"⚠️ Persistent browser failed: {e1}, trying CDP fallback...")
159 |                 try:
160 |                     browser, page = await connect_cdp(p, self.cdp_url)
    |                     ^^^^^^^
161 |                 except Exception as e2:
162 |                     print(f"⚠️ CDP fallback also failed: {e2}")
    |
help: Prefix it with an underscore or any other dummy variable pattern

BLE001 Do not catch blind exception: `Exception`
   --> src/automation/easy_apply.py:161:24
    |
159 |                 try:
160 |                     browser, page = await connect_cdp(p, self.cdp_url)
161 |                 except Exception as e2:
    |                        ^^^^^^^^^
162 |                     print(f"⚠️ CDP fallback also failed: {e2}")
163 |                     return {"status": "FAILED", "reason": str(e2)}
    |

BLE001 Do not catch blind exception: `Exception`
   --> src/automation/easy_apply.py:180:24
    |
178 |                         await easy_apply_btn.first.click()
179 |                         await self._human_delay(1.5, 3.0)
180 |                 except Exception as e:
    |                        ^^^^^^^^^
181 |                     print(f"⚠️ Navigation / trigger warning: {e}")
    |

ASYNC210 Async functions should not call blocking HTTP methods
  --> src/browser/cdp_connector.py:33:14
   |
31 |     version_url = f"{cdp_url}/json/version"
32 |     try:
33 |         with urllib.request.urlopen(version_url, timeout=5) as resp:
   |              ^^^^^^^^^^^^^^^^^^^^^^
34 |             info = json.loads(resp.read().decode())
35 |     except Exception as e:
   |

BLE001 Do not catch blind exception: `Exception`
  --> src/filter/job_filter.py:51:20
   |
49 |                 with open(filepath, "r") as f:
50 |                     payload = json.load(f)
51 |             except Exception as e:
   |                    ^^^^^^^^^
52 |                 print(f"⚠️ Error reading {fname}: {e}")
53 |                 continue
   |

ASYNC230 Async functions should not open files with blocking methods like `open`
  --> src/pdf_engine/generator.py:24:14
   |
23 |         # Read CSS content to inject it directly
24 |         with open(self.css_path, 'r') as f:
   |              ^^^^
25 |             css_content = f.read()
   |

DTZ011 `datetime.date.today()` used
   --> src/resume_store/models.py:171:35
    |
169 |         total_days = 0
170 |         for exp in self.experience_history:
171 |             end = exp.end_date or date.today()
    |                                   ^^^^^^^^^^^^
172 |             total_days += (end - exp.start_date).days
173 |         return round(total_days / 365.25, 1)
    |
help: Use `datetime.datetime.now(tz=...).date()` instead

BLE001 Do not catch blind exception: `Exception`
  --> src/scraper/job_finder.py:29:16
   |
27 |             with open(self.db_file, "r") as f:
28 |                 return json.load(f)
29 |         except Exception:
   |                ^^^^^^^^^
30 |             return {"job_ids": {}, "composite_hashes": {}}
   |

DTZ003 `datetime.datetime.utcnow()` used
  --> src/scraper/job_finder.py:71:15
   |
69 |         """Registers a job into the master deduplication index."""
70 |         data = self.load_processed_jobs()
71 |         now = datetime.datetime.utcnow().isoformat() + "Z"
   |               ^^^^^^^^^^^^^^^^^^^^^^^^^^
72 |         c_hash = self.generate_composite_hash(company, title)
   |
help: Use `datetime.datetime.now(tz=...)` instead

RUF013 PEP 484 prohibits implicit `Optional`
  --> src/scraper/job_finder.py:90:21
   |
88 |         keywords: str,
89 |         location: str = "Remote",
90 |         work_types: list[str] = None,
   |                     ^^^^^^^^^
91 |         experience_levels: list[str] = None,
92 |         time_posted: str = "past_week"
   |
help: Convert to `T | None`

RUF013 PEP 484 prohibits implicit `Optional`
  --> src/scraper/job_finder.py:91:28
   |
89 |         location: str = "Remote",
90 |         work_types: list[str] = None,
91 |         experience_levels: list[str] = None,
   |                            ^^^^^^^^^
92 |         time_posted: str = "past_week"
93 |     ) -> str:
   |
help: Convert to `T | None`

BLE001 Do not catch blind exception: `Exception`
   --> src/scraper/job_finder.py:144:20
    |
142 |                 print("🌐 Launching single persistent Chrome session for batch search...")
143 |                 context, page = await launch_persistent_browser(p)
144 |             except Exception as e1:
    |                    ^^^^^^^^^
145 |                 print(f"⚠️ Persistent browser launch failed: {e1}, trying CDP fallback...")
146 |                 try:
    |

RUF059 Unpacked variable `browser` is never used
   --> src/scraper/job_finder.py:147:21
    |
145 |                 print(f"⚠️ Persistent browser launch failed: {e1}, trying CDP fallback...")
146 |                 try:
147 |                     browser, page = await connect_cdp(p, self.cdp_url)
    |                     ^^^^^^^
148 |                 except Exception as e2:
149 |                     print(f"⚠️ CDP fallback also failed: {e2}")
    |
help: Prefix it with an underscore or any other dummy variable pattern

BLE001 Do not catch blind exception: `Exception`
   --> src/scraper/job_finder.py:148:24
    |
146 |                 try:
147 |                     browser, page = await connect_cdp(p, self.cdp_url)
148 |                 except Exception as e2:
    |                        ^^^^^^^^^
149 |                     print(f"⚠️ CDP fallback also failed: {e2}")
150 |                     return all_extracted_jobs
    |

S110 `try`-`except`-`pass` detected, consider logging the exception
   --> src/scraper/job_finder.py:226:33
    |
224 |   …                                 if raw_desc and len(raw_desc.strip()) > 20:
225 |   …                                     desc_text = raw_desc.strip()
226 | / …                         except Exception:
227 | | …                             pass
    | |__________________________________^
228 |   …
229 |   …                     raw_job = {
    |

BLE001 Do not catch blind exception: `Exception`
   --> src/scraper/job_finder.py:226:40
    |
224 | …                             if raw_desc and len(raw_desc.strip()) > 20:
225 | …                                 desc_text = raw_desc.strip()
226 | …                     except Exception:
    |                              ^^^^^^^^^
227 | …                         pass
    |

BLE001 Do not catch blind exception: `Exception`
   --> src/scraper/job_finder.py:247:32
    |
245 |                             extracted_count += 1
246 |
247 |                         except Exception as e:
    |                                ^^^^^^^^^
248 |                             print(f"⚠️ Error extracting card {card_idx}: {e}")
    |

BLE001 Do not catch blind exception: `Exception`
   --> src/scraper/job_finder.py:250:24
    |
248 |                             print(f"⚠️ Error extracting card {card_idx}: {e}")
249 |
250 |                 except Exception as e:
    |                        ^^^^^^^^^
251 |                     print(f"⚠️ Search navigation error for '{keywords}': {e}")
    |

BLE001 Do not catch blind exception: `Exception`
  --> src/tailor/llm_provider.py:43:20
   |
41 |                 from google import genai
42 |                 self.client = genai.Client(api_key=self.api_key)
43 |             except Exception as e:
   |                    ^^^^^^^^^
44 |                 print(f"⚠️ Failed to initialize Gemini Client: {e}")
   |

BLE001 Do not catch blind exception: `Exception`
   --> src/tailor/llm_provider.py:161:20
    |
159 |                 print("✨ Using Primary Gemini API Provider...")
160 |                 return self.gemini.generate_tailored_bullets(job_description, profile)
161 |             except Exception as e:
    |                    ^^^^^^^^^
162 |                 print(f"⚠️ Gemini API failed: {e}. Falling back to Ollama...")
    |

BLE001 Do not catch blind exception: `Exception`
   --> src/tailor/llm_provider.py:172:20
    |
170 |                 print("✨ Using Primary Gemini API Provider...")
171 |                 return self.gemini.answer_screening_question(question, profile)
172 |             except Exception as e:
    |                    ^^^^^^^^^
173 |                 print(f"⚠️ Gemini API failed: {e}. Falling back to Ollama...")
    |

BLE001 Do not catch blind exception: `Exception`
  --> src/tailor/resume_tailorer.py:47:20
   |
45 |                     print(f"🤖 AI tailored {len(ai_bullets)} top achievements!")
46 |                     tailored_data["experience_history"][0]["achievements"] = ai_bullets
47 |             except Exception as e:
   |                    ^^^^^^^^^
48 |                 print(f"⚠️ AI Bullet tailoring skipped (using heuristic): {e}")
   |

ASYNC230 Async functions should not open files with blocking methods like `open`
  --> src/ui/app.py:34:26
   |
32 |                 file_path = os.path.join(PENDING_DIR, filename)
33 |                 try:
34 |                     with open(file_path, 'r') as f:
   |                          ^^^^
35 |                         jobs.append(json.load(f))
36 |                 except Exception as e:
   |

BLE001 Do not catch blind exception: `Exception`
  --> src/ui/app.py:36:24
   |
34 |                     with open(file_path, 'r') as f:
35 |                         jobs.append(json.load(f))
36 |                 except Exception as e:
   |                        ^^^^^^^^^
37 |                     print(f"Error reading {filename}: {e}")
38 |     return {"jobs": jobs}
   |

ASYNC230 Async functions should not open files with blocking methods like `open`
  --> src/ui/app.py:70:14
   |
68 |             print(f"PDF generated at {pdf_path}")
69 |             
70 |         with open(approved_path, 'w') as f:
   |              ^^^^
71 |             json.dump(payload, f, indent=2)
   |

BLE001 Do not catch blind exception: `Exception`
  --> src/ui/app.py:74:12
   |
73 |         return {"status": "success", "message": f"Job {job_id} approved and saved.", "path": approved_path, "pdf_path": payload.get("g…
74 |     except Exception as e:
   |            ^^^^^^^^^
75 |         import traceback
76 |         traceback.print_exc()
   |

N999 Invalid module name: '01_test_playwright_context'
--> verify/01_test_playwright_context.py:1:1

N999 Invalid module name: '02_test_resume_store'
--> verify/02_test_resume_store.py:1:1

BLE001 Do not catch blind exception: `Exception`
   --> verify/02_test_resume_store.py:101:12
    |
 99 |         print("=" * 60)
100 |
101 |     except Exception as e:
    |            ^^^^^^^^^
102 |         print(f"❌ Schema Validation Failed!\n{e}")
103 |         import traceback
    |

N999 Invalid module name: '03_test_approval_gate'
--> verify/03_test_approval_gate.py:1:1

N999 Invalid module name: '04_test_playwright_cdp_connect'
--> verify/04_test_playwright_cdp_connect.py:1:1

N999 Invalid module name: '05_test_pdf_generation'
--> verify/05_test_pdf_generation.py:1:1

N999 Invalid module name: '06_audit_resume_accuracy'
--> verify/06_audit_resume_accuracy.py:1:1

N999 Invalid module name: '07_test_easy_apply_flow'
--> verify/07_test_easy_apply_flow.py:1:1

ASYNC230 Async functions should not open files with blocking methods like `open`
   --> verify/07_test_easy_apply_flow.py:108:10
    |
106 |     # Write temporary HTML file
107 |     temp_html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_mock_modal.html"))
108 |     with open(temp_html_path, "w") as f:
    |          ^^^^
109 |         f.write(MOCK_MODAL_HTML)
    |

ASYNC230 Async functions should not open files with blocking methods like `open`
   --> verify/07_test_easy_apply_flow.py:113:10
    |
111 |     # Load test resume profile
112 |     json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json"))
113 |     with open(json_path, "r") as f:
    |          ^^^^
114 |         resume_data = json.load(f)
    |

N999 Invalid module name: '08_test_job_finder_and_tailorer'
--> verify/08_test_job_finder_and_tailorer.py:1:1

N999 Invalid module name: '09_test_llm_integration'
--> verify/09_test_llm_integration.py:1:1

F841 Local variable `profile` is assigned to but never used
  --> verify/09_test_llm_integration.py:26:5
   |
24 |     with open(json_path, 'r') as f:
25 |         data = json.load(f)
26 |     profile = ResumeProfile(**data)
   |     ^^^^^^^
27 |
28 |     # 2. Test Pydantic Structured Schema Specs
   |
help: Remove assignment to unused variable `profile`

N999 Invalid module name: '10_test_linkedin_live_flow'
--> verify/10_test_linkedin_live_flow.py:1:1

RUF059 Unpacked variable `browser` is never used
  --> verify/10_test_linkedin_live_flow.py:35:13
   |
33 |         # Strategy A: Attach to existing Chrome on port 9222
34 |         try:
35 |             browser, page = await connect_cdp(p, cdp_url)
   |             ^^^^^^^
36 |             title = await page.title()
37 |             print(f"✅ CDP attached to live Chrome! Active tab: {title}")
   |
help: Prefix it with an underscore or any other dummy variable pattern

BLE001 Do not catch blind exception: `Exception`
  --> verify/10_test_linkedin_live_flow.py:39:16
   |
37 |             print(f"✅ CDP attached to live Chrome! Active tab: {title}")
38 |             connected = True
39 |         except Exception as e:
   |                ^^^^^^^^^
40 |             print(f"⚠️ CDP attach failed: {e}")
   |

BLE001 Do not catch blind exception: `Exception`
  --> verify/10_test_linkedin_live_flow.py:53:20
   |
51 |                 connected = True
52 |                 await context.close()
53 |             except Exception as e:
   |                    ^^^^^^^^^
54 |                 print(f"⚠️ Persistent launch also failed: {e}")
   |

N999 Invalid module name: '11_test_main_orchestrator'
--> verify/11_test_main_orchestrator.py:1:1

PLW1510 `subprocess.run` without explicit `check` argument
  --> verify/11_test_main_orchestrator.py:32:14
   |
30 |     print("\n🔍 Step 2: Testing main.py CLI Parser...")
31 |     cmd = [sys.executable, "main.py", "--help"]
32 |     result = subprocess.run(cmd, capture_output=True, text=True)
   |              ^^^^^^^^^^^^^^
33 |     assert result.returncode == 0
34 |     assert "search" in result.stdout
   |
help: Add explicit `check=False`

N999 Invalid module name: '12_test_search_and_filter'
--> verify/12_test_search_and_filter.py:1:1

N999 Invalid module name: '13_test_job_finder_optimization'
--> verify/13_test_job_finder_optimization.py:1:1

Found 58 errors.
No fixes available (8 hidden fixes can be enabled with the `--unsafe-fixes` option).
(venv) yeshwinmanjunath@Yeshwins-MacBook-Air linkedinjobsearchautomation % 