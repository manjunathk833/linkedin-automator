import json
import os
import re


def clean_html(text):
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return clean.replace("&amp;", "&").replace("&nbsp;", " ").strip()


def run_detailed_audit():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_path = os.path.join(root, "singlepageresume.json")
    mapped_path = os.path.join(root, "data", "resume_profile.json")

    with open(src_path) as f:
        src = json.load(f)
    with open(mapped_path) as f:
        mapped = json.load(f)

    print("===============================================================")
    print("           DETAILED RESUME CONTENT COMPARISON AUDIT           ")
    print("===============================================================\n")

    # 1. Basics
    print("--- 1. PERSONAL DETAILS / BASICS ---")
    b = src.get("basics", {})
    m_p = mapped.get("personal_details", {})
    print(f"Source Name     : {b.get('name')}")
    print(f"Mapped Name     : {m_p.get('full_name')}")
    print(f"Source Headline : {b.get('headline')}")
    print(f"Mapped Headline : {m_p.get('label')}")
    print(f"Source Email    : {b.get('email')}")
    print(f"Mapped Email    : {m_p.get('email')}")
    print(f"Source Phone    : {b.get('phone')}")
    print(f"Mapped Phone    : {m_p.get('phone')}")
    print(f"Source Location : {b.get('location')}")
    print(f"Mapped Location : {m_p.get('location')}\n")

    # 2. Experience
    print("--- 2. EXPERIENCE ITEMS ---")
    s_exp = [i for i in src["sections"]["experience"]["items"] if not i.get("hidden")]
    m_exp = mapped["experience_history"]
    for idx, (s, m) in enumerate(zip(s_exp, m_exp)):
        print(f"Item {idx + 1}:")
        print(f"  Source : {s.get('position')} at {s.get('company')} ({s.get('period')})")
        print(f"  Mapped : {m.get('role')} at {m.get('company')} ({m.get('start_date')} to {m.get('end_date')})")
        s_bullets = [clean_html(li) for li in re.findall(r"<li>(.*?)</li>", s.get("description", ""))]
        m_bullets = m.get("achievements", [])
        print(f"  Bullets count: Source={len(s_bullets)}, Mapped={len(m_bullets)}")
        for b_idx, (sb, mb) in enumerate(zip(s_bullets, m_bullets)):
            match = "✅" if sb == mb else "❌"
            print(f"    Bullet {b_idx + 1} {match}:")
            print(f"      SRC: {sb}")
            print(f"      MAP: {mb}")
    print()

    # 3. Education
    print("--- 3. EDUCATION ---")
    s_edu = [i for i in src["sections"]["education"]["items"] if not i.get("hidden")]
    m_edu = mapped["education"]
    for s, m in zip(s_edu, m_edu):
        print(f"  Source : {s.get('school')} | {s.get('degree')} | {s.get('grade')}")
        print(f"  Mapped : {m.get('institution')} | {m.get('study_type')} in {m.get('area')} | {m.get('gpa')}\n")

    # 4. Skills
    print("--- 4. SKILLS ---")
    s_skills = [i for i in src["sections"]["skills"]["items"] if not i.get("hidden")]
    print("  Source Skill Categories:")
    for cat in s_skills:
        print(f"    - {cat.get('name')}: {', '.join(cat.get('keywords', []))}")
    print("  Mapped Skills Matrix Count:", len(mapped.get("skills_matrix", {})))
    print()

    # 5. Certifications
    print("--- 5. CERTIFICATIONS ---")
    s_certs = [i for i in src["sections"]["certifications"]["items"] if not i.get("hidden")]
    m_certs = mapped["certifications"]
    print(f"  Source Active Certs ({len(s_certs)}):")
    for c in s_certs:
        print(f"    - {c.get('title')} ({c.get('issuer')}, {c.get('date')})")
    print(f"  Mapped Certs ({len(m_certs)}):")
    for c in m_certs:
        print(f"    - {c.get('name')} ({c.get('issuer')}, {c.get('issue_date')})")
    print()

    # 6. Awards
    print("--- 6. AWARDS ---")
    s_awards = [i for i in src["sections"]["awards"]["items"] if not i.get("hidden")]
    m_awards = mapped["awards"]
    print(f"  Source Awards ({len(s_awards)}):")
    for a in s_awards:
        print(f"    - {a.get('title')} from {a.get('awarder')} ({a.get('date')})")
    print(f"  Mapped Awards ({len(m_awards)}):")
    for a in m_awards:
        print(f"    - {a.get('title')} from {a.get('awarder')} ({a.get('award_date')})")


if __name__ == "__main__":
    run_detailed_audit()
