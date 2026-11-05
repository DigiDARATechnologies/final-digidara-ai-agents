"""Generates the public, crawlable pages (agents, pricing, colleges, FAQ), sitemap.xml and llms.txt.

The SkillDARA app is a single-page app behind a login, so search engines and AI
assistants only see one page. These plain HTML pages give them real, indexable
content. They load only a CSS file (the site's security policy forbids inline
styles and scripts). Run from the repository root:

    python scripts/generate_seo_pages.py
"""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SITE = "https://skilldara.com"
TODAY = date.today().isoformat()
SUPPORT = "support@digidaraaiagents.com"

AGENTS = [
    {
        "slug": "coding-practice", "name": "Coding Practice", "cat": "Practice",
        "tag": "Practise coding with real test cases and an AI tutor",
        "lead": "Solve real coding problems and check your code against sandboxed test runs, including hidden test cases, so you know it works before a placement test or interview.",
        "does": [
            "Practise problems by course and topic, from basics to Professional level (Python, Pandas, NumPy, HTML, CSS and more).",
            "Run and submit your code against sandboxed tests, including hidden test cases.",
            "Get step-by-step help from an AI tutor when you are stuck.",
            "Track what you have solved and where you need more practice.",
        ],
        "for": "Students preparing for coding rounds, placement tests and technical interviews.",
    },
    {
        "slug": "aptitude-trainer", "name": "Aptitude Trainer", "cat": "Practice",
        "tag": "Quantitative, logical and verbal practice with explanations",
        "lead": "Practise the aptitude topics placement tests ask for, in timed tests, and learn from a step-by-step explanation after every question.",
        "does": [
            "Practise quantitative aptitude, logical reasoning and verbal ability.",
            "Take timed practice tests and mixed tests tuned to a role.",
            "Read step-by-step explanations for every question.",
            "See your test history and the priority topics to work on next.",
        ],
        "for": "Students preparing for campus placement aptitude rounds and competitive hiring tests.",
    },
    {
        "slug": "communication-coach", "name": "Communication Coach", "cat": "Practice",
        "tag": "Speaking, pronunciation and writing practice scored by AI",
        "lead": "Improve how you speak and write for interviews and the workplace, with AI scoring and feedback on every attempt.",
        "does": [
            "Practise pronunciation and speaking with AI scoring.",
            "Practise writing and get suggested rewrites.",
            "Take daily challenges to build a habit.",
            "Track your progress over time.",
        ],
        "for": "Students and job seekers who want to speak and write with confidence in interviews and at work.",
    },
    {
        "slug": "mock-interview", "name": "Mock Interview Agent", "cat": "Interview",
        "tag": "Technical and HR mock interviews with feedback on every answer",
        "lead": "Rehearse real interview rounds before the day. Each answer is scored and explained, and you can talk to the interviewer by voice.",
        "does": [
            "Practise technical and HR interview rounds.",
            "Get a score and feedback on every answer.",
            "Have a voice conversation with the interviewer.",
            "Read a final report on how the whole interview went.",
        ],
        "for": "Students and job seekers getting ready for placement interviews.",
    },
    {
        "slug": "resume-builder", "name": "Resume Builder", "cat": "Careers",
        "tag": "Build an ATS-friendly resume in a guided workflow",
        "lead": "Create, import, analyse and export a resume that applicant tracking systems can read, with guidance at every step.",
        "does": [
            "Build a resume step by step with a guided workflow.",
            "Import an existing resume and improve it.",
            "Analyse it for ATS-friendliness.",
            "Export a clean, professional resume.",
        ],
        "for": "Students, fresh graduates and professionals applying for jobs.",
    },
    {
        "slug": "job-agent", "name": "Job Agent", "cat": "Careers",
        "tag": "Find jobs that match your profile, ranked by fit",
        "lead": "Tell the Job Agent about your skills and goals, and it finds matching roles and ranks them with a fit score you can understand.",
        "does": [
            "Find roles that match your profile, including other careers and remote jobs.",
            "See an explainable fit score for each role.",
            "Keep your search organised in one place.",
        ],
        "for": "Fresh graduates and job seekers looking for roles that fit their skills.",
    },
    {
        "slug": "capstone-project", "name": "Capstone Project Agent", "cat": "Projects",
        "tag": "Take a project from topic to graded submission",
        "lead": "Pick a project topic, build it, submit it and get it reviewed, with eligibility checks and a 7-day timer to keep you on track.",
        "does": [
            "Choose a project topic that fits your goals.",
            "Work to a 7-day timer after eligibility checks.",
            "Submit your project and get a graded review.",
            "Answer viva questions on your own project.",
        ],
        "for": "Students who need a graded project to show on a resume or for a course.",
    },
    {
        "slug": "ai-certification", "name": "AI Certification Agent", "cat": "Certify",
        "tag": "Chat-based assessments and downloadable certificates",
        "lead": "Take chat-based assessments, see where you stand on a leaderboard and download a PDF certificate to show employers.",
        "does": [
            "Take assessments in a chat format.",
            "Climb a leaderboard against other learners.",
            "Download a PDF certificate when you pass.",
        ],
        "for": "Students and professionals who want proof of their skills.",
    },
]

PLANS = [
    ("Free", "₹0", "25 coins on signup", "Try the agents and see how SkillDARA works."),
    ("Basic", "₹399", "250 coins", "For getting started and light, occasional use."),
    ("Standard", "₹799", "500 coins", "For regular learners who use several agents each week."),
    ("Premium", "₹999", "750 coins", "For heavy daily use across every agent."),
]

FAQS = [
    ("What is SkillDARA?", "SkillDARA is a platform of eight AI agents that help students and professionals upgrade their skills and become job-ready: coding practice, aptitude training, communication coaching, mock interviews, a resume builder, a job agent, capstone projects and AI certification, all under one account."),
    ("Who is SkillDARA for?", "Students preparing for placements, fresh graduates, job seekers and working professionals who want to upgrade their skills. Colleges and training institutes can also use it to run assessments and track their learners."),
    ("Do I need to pay to start?", "No. You can create a free account and get 25 free coins. When you want more usage, you can buy coins in one-time packs inside the app."),
    ("How do coins work?", "Each agent request uses a few coins. Coins are bought once, never expire, and your balance is shown inside the app. Prices are before GST."),
    ("Which AI agents does SkillDARA have?", "Coding Practice, Aptitude Trainer, Communication Coach, Mock Interview Agent, Resume Builder, Job Agent, Capstone Project Agent and AI Certification Agent."),
    ("Can my college or institute use SkillDARA?", f"Yes. Organizations get an admin dashboard, staff and class management, assessments with proctoring and reports. Contact {SUPPORT} and we will set it up."),
    ("Is my data safe?", "Sessions are secured, agent requests are signed, and privacy controls follow data-protection principles including data export and account deletion."),
]

COLLEGE = [
    ("Organization dashboard", "See learner activity and progress across your whole institution in one place."),
    ("Class and staff management", "Add staff, upload student lists and organise learners by class."),
    ("Assessments with proctoring", "Run knowledge tests and assessments, and review proctoring reports."),
    ("Reports and leaderboards", "Track results, compare cohorts and spot students who need help."),
]

e = html.escape


def head(title: str, desc: str, path: str, extra_ld: list[dict] | None = None) -> str:
    url = f"{SITE}{path}"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False)}</script>\n    ' for d in (extra_ld or []))
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{e(title)}</title>
    <meta name="description" content="{e(desc)}" />
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
    <meta name="theme-color" content="#17348e" />
    <link rel="canonical" href="{url}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="SkillDARA" />
    <meta property="og:title" content="{e(title)}" />
    <meta property="og:description" content="{e(desc)}" />
    <meta property="og:url" content="{url}" />
    <meta property="og:image" content="{SITE}/og-image.png" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{e(title)}" />
    <meta name="twitter:description" content="{e(desc)}" />
    <meta name="twitter:image" content="{SITE}/og-image.png" />
    {ld}<link rel="icon" type="image/png" href="/favicon.png" />
    <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
    <link rel="stylesheet" href="/seo-pages.css" />
  </head>
"""


def shell(body: str) -> str:
    return f"""  <body>
    <header class="sp-nav">
      <div class="sp-wrap sp-nav-inner">
        <a href="/" class="sp-brand"><img src="/skilldara-logo.png" alt="SkillDARA" height="40" /></a>
        <nav aria-label="Primary">
          <a href="/agents/">Agents</a>
          <a href="/pricing/">Pricing</a>
          <a href="/for-colleges/">For colleges</a>
          <a href="/faq/">FAQ</a>
        </nav>
        <a class="sp-btn" href="/login">Start free</a>
      </div>
    </header>
    <main class="sp-wrap sp-main">
{body}
    </main>
    <footer class="sp-foot">
      <div class="sp-wrap">
        <p><strong>SkillDARA</strong> by DigiDARA Technologies. AI agents for students and professionals to upgrade skills and get job-ready.</p>
        <p><a href="/agents/">Agents</a> · <a href="/pricing/">Pricing</a> · <a href="/for-colleges/">For colleges</a> · <a href="/faq/">FAQ</a> · <a href="mailto:{SUPPORT}">{SUPPORT}</a></p>
      </div>
    </footer>
  </body>
</html>
"""


def cta(text: str = "Start free with 25 coins. No setup needed.") -> str:
    return f"""      <section class="sp-cta">
        <h2>{e(text)}</h2>
        <p>Create your free account and open your first agent in minutes.</p>
        <a class="sp-btn" href="/login">Start free</a>
      </section>"""


def crumbs(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE}{p}"} for i, (n, p) in enumerate(items)
        ],
    }


def write(path: str, content: str) -> None:
    out = PUBLIC / path.strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def agent_page(a: dict) -> None:
    path = f"/agents/{a['slug']}/"
    title = f"{a['name']} for Students | SkillDARA"
    desc = f"{a['tag']}. {a['lead']}"[:300]
    app = {
        "@context": "https://schema.org", "@type": "SoftwareApplication", "name": f"SkillDARA {a['name']}",
        "applicationCategory": "EducationalApplication", "operatingSystem": "Web", "url": f"{SITE}{path}",
        "description": a["lead"], "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR"},
        "publisher": {"@type": "Organization", "name": "DigiDARA Technologies", "url": SITE},
    }
    others = "".join(
        f'<li><a href="/agents/{o["slug"]}/">{e(o["name"])}</a></li>' for o in AGENTS if o["slug"] != a["slug"]
    )
    body = f"""      <nav class="sp-crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / <a href="/agents/">Agents</a> / {e(a['name'])}</nav>
      <span class="sp-pill">{e(a['cat'])}</span>
      <h1>{e(a['name'])}: {e(a['tag'][0].lower() + a['tag'][1:])}</h1>
      <p class="sp-lead">{e(a['lead'])}</p>
      <h2>What you can do</h2>
      <ul class="sp-list">{''.join(f'<li>{e(x)}</li>' for x in a['does'])}</ul>
      <h2>Who it is for</h2>
      <p>{e(a['for'])}</p>
      <h2>Part of SkillDARA</h2>
      <p>The {e(a['name'])} is one of eight AI agents in a single SkillDARA account. Start free with 25 coins; coins are one-time and never expire.</p>
      <h2>Other agents</h2>
      <ul class="sp-chips">{others}</ul>
{cta()}"""
    write(path, head(title, desc, path, [app, crumbs([("Home", "/"), ("Agents", "/agents/"), (a["name"], path)])]) + shell(body))


def agents_index() -> None:
    path = "/agents/"
    title = "8 AI Agents for Students: Coding, Aptitude, Interviews, Resume & Jobs | SkillDARA"
    desc = "Meet the eight SkillDARA AI agents for students and professionals: coding practice, aptitude, communication, mock interviews, resume builder, jobs, capstone projects and certification."
    cards = "".join(
        f'<a class="sp-card" href="/agents/{a["slug"]}/"><span class="sp-pill">{e(a["cat"])}</span><h3>{e(a["name"])}</h3><p>{e(a["tag"])}.</p></a>'
        for a in AGENTS
    )
    lst = {
        "@context": "https://schema.org", "@type": "ItemList", "name": "SkillDARA AI agents",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": a["name"], "url": f"{SITE}/agents/{a['slug']}/"}
            for i, a in enumerate(AGENTS)
        ],
    }
    body = f"""      <nav class="sp-crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / Agents</nav>
      <h1>Eight AI agents to upgrade your skills and get job-ready</h1>
      <p class="sp-lead">One SkillDARA account gives students and professionals every agent they need, from daily practice to interviews and job search.</p>
      <div class="sp-grid">{cards}</div>
{cta()}"""
    write(path, head(title, desc, path, [lst, crumbs([("Home", "/"), ("Agents", path)])]) + shell(body))


def pricing_page() -> None:
    path = "/pricing/"
    title = "Pricing: Free to Start, One-Time Coin Packs | SkillDARA"
    desc = "Start free with 25 coins. Buy one-time coin packs from ₹399. Coins never expire. Prices are before GST."
    rows = "".join(
        f'<div class="sp-card"><h3>{e(n)}</h3><p class="sp-price">{e(p)}</p><p><strong>{e(c)}</strong></p><p>{e(t)}</p></div>'
        for n, p, c, t in PLANS
    )
    prod = {
        "@context": "https://schema.org", "@type": "Product", "name": "SkillDARA coins",
        "description": "One-time coin packs used by SkillDARA AI agents. Coins never expire.",
        "brand": {"@type": "Brand", "name": "SkillDARA"},
        "offers": [
            {"@type": "Offer", "name": n, "price": p.replace("₹", ""), "priceCurrency": "INR", "url": f"{SITE}/pricing/"}
            for n, p, _, _ in PLANS
        ],
    }
    body = f"""      <nav class="sp-crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / Pricing</nav>
      <h1>Simple, one-time coin packs</h1>
      <p class="sp-lead">Each agent request uses a few coins. Coins are bought once and never expire. Prices are before GST.</p>
      <div class="sp-grid sp-grid-4">{rows}</div>
{cta()}"""
    write(path, head(title, desc, path, [prod, crumbs([("Home", "/"), ("Pricing", path)])]) + shell(body))


def colleges_page() -> None:
    path = "/for-colleges/"
    title = "For Colleges: Track Placement Readiness & Run Assessments | SkillDARA"
    desc = f"SkillDARA for colleges and institutes: an organization dashboard, class and staff management, proctored assessments and reports. Contact {SUPPORT}."
    rows = "".join(f'<div class="sp-card"><h3>{e(t)}</h3><p>{e(x)}</p></div>' for t, x in COLLEGE)
    body = f"""      <nav class="sp-crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / For colleges</nav>
      <h1>Know how ready your students are for placements</h1>
      <p class="sp-lead">Give every student the eight SkillDARA AI agents and see their progress in one dashboard.</p>
      <div class="sp-grid">{rows}</div>
      <section class="sp-cta">
        <h2>Bring SkillDARA to your college</h2>
        <p>Write to <a href="mailto:{SUPPORT}">{SUPPORT}</a> and we will set up your organization.</p>
        <a class="sp-btn" href="mailto:{SUPPORT}?subject=SkillDARA%20for%20our%20college">Talk to us</a>
      </section>"""
    write(path, head(title, desc, path, [crumbs([("Home", "/"), ("For colleges", path)])]) + shell(body))


def faq_page() -> None:
    path = "/faq/"
    title = "FAQ: Questions About SkillDARA AI Agents | SkillDARA"
    desc = "Answers about SkillDARA: who it is for, the eight AI agents, free coins, pricing, colleges and data safety."
    faq = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQS
        ],
    }
    items = "".join(f"<h2>{e(q)}</h2><p>{e(a)}</p>" for q, a in FAQS)
    body = f"""      <nav class="sp-crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / FAQ</nav>
      <h1>Frequently asked questions</h1>
      {items}
{cta()}"""
    write(path, head(title, desc, path, [faq, crumbs([("Home", "/"), ("FAQ", path)])]) + shell(body))


def sitemap() -> None:
    urls = [("/", "1.0", "weekly"), ("/agents/", "0.9", "weekly")]
    urls += [(f"/agents/{a['slug']}/", "0.8", "monthly") for a in AGENTS]
    urls += [("/pricing/", "0.8", "monthly"), ("/for-colleges/", "0.7", "monthly"), ("/faq/", "0.7", "monthly"), ("/login", "0.4", "monthly")]
    rows = "\n".join(
        f"  <url><loc>{SITE}{p}</loc><lastmod>{TODAY}</lastmod><changefreq>{f}</changefreq><priority>{pr}</priority></url>"
        for p, pr, f in urls
    )
    (PUBLIC / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n',
        encoding="utf-8",
    )


def llms() -> None:
    agents = "\n".join(f"- [{a['name']}]({SITE}/agents/{a['slug']}/): {a['tag']}." for a in AGENTS)
    (PUBLIC / "llms.txt").write_text(
        f"""# SkillDARA

> SkillDARA ({SITE}) is a platform of eight AI agents for students and professionals to upgrade their skills and get job-ready. It is built by DigiDARA Technologies. Start free with 25 coins.

## What it offers
{agents}
- One account for all agents, with chat history across devices.
- For colleges: an organization dashboard, class and staff management, proctored assessments and reports.

## Audience
Students preparing for placements, fresh graduates, job seekers and working professionals. Colleges and training institutes as organizations.

## Pricing
Free to start (25 coins). One-time coin packs: Basic Rs 399 (250 coins), Standard Rs 799 (500 coins), Premium Rs 999 (750 coins). Coins never expire. Prices are before GST.

## Links
- Home: {SITE}/
- All agents: {SITE}/agents/
- Pricing: {SITE}/pricing/
- For colleges: {SITE}/for-colleges/
- FAQ: {SITE}/faq/
- Login / sign up: {SITE}/login
- Contact: {SUPPORT}
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    agents_index()
    for agent in AGENTS:
        agent_page(agent)
    pricing_page()
    colleges_page()
    faq_page()
    sitemap()
    llms()
    print("generated", len(AGENTS) + 4, "pages, sitemap.xml and llms.txt")
