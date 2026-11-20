# Career Growth Agent: notes for Claude

I'm a fresher building this solo as a pitch prototype for my seniors (pitch on 7 Dec 2026).
Explain what you change in simple terms, and give me commands to run when I must do something myself.

## What this is
An AI career agent. It coaches each employee privately (skill gaps, roadmap, free courses, mentor chat,
role fit, promotion readiness). Leads, managers and leadership see only aggregated, privacy-safe team views.
It runs on a synthetic company, "Nimbus Tech" (27 people, 4 teams, bands B1-B4).

## Hard rules
1. **Privacy:** pages never query personal tables directly. All personal reads and writes go through
   `core/access.py`. Upward views use `core/aggregate.py` (groups under 5 people return None). A name goes
   upward only with `share_consent`. Never weaken these; `tests/test_core.py` must keep passing.
2. **Free tools only:** LLMs via `core/llm.py` (Gemini free tier → Groq free tier → local Ollama). Don't add
   paid APIs or paid services.
3. **Courses only from `data/catalog.yaml`** (Microsoft Learn, freeCodeCamp, Kaggle Learn). The AI must never
   invent course names or links. Suggestions should cover at least 2 platforms.
4. Send only synthetic data to free AI tiers.
5. Keep it simple: plain Python, Streamlit, built-in sqlite3. No new frameworks without asking me.

## Commands (Windows PowerShell)
- Install: `uv sync`
- Tests: `uv run pytest`
- Reset demo data: `uv run python scripts/seed.py`
- Run app: `uv run streamlit run app.py` → http://localhost:8501
- Export synthetic dataset: `uv run python scripts/export_dataset.py`
- Check course links: `uv run python scripts/check_links.py`
- Secrets: `.streamlit/secrets.toml` (copy from `.example`; git-ignored, never commit or print keys)
- Check the LLM connection: `uv run python scripts/check_llm.py`

## Model setup
- Order: Gemini free tier → Groq free tier → local Ollama (`core/llm.py`).
- Gemini: set `LLM_MODEL` in secrets.toml to a model that answers (`gemini-3.5-flash` worked on 20 Nov 2026;
  `gemini-flash-latest` gave 503s).
- Groq: the default is now `openai/gpt-oss-120b`. `llama-3.3-70b-versatile` is retired.
- Ollama: `llama3.2` (run `ollama serve` first).

## Map
- `app.py`: navigation + sidebar persona switcher
- `views/`: my_growth, upload, roadmap, mentor (chatbot), my_team (B2/B3), org (B4)
- `core/`: access (privacy), aggregate, llm, extract, gaps, readiness, recommend, rolefit, mentor, plan, github,
  db, seed, synthetic, taxonomy, ui
- `data/`: taxonomy.yaml, catalog.yaml, sample_docs/, synthetic/ (CSVs + documents + ground truth)
- `notebooks/`: Colab notebooks (extraction playground; dataset + extraction accuracy)
- `tests/`: test_core (privacy, scoring), test_seed (demo-story data facts), test_pages (page smoke tests)
- `scripts/`: seed, export_dataset, check_links, check_llm (LLM connection smoke test; never prints keys)

## Sprint plan (story IDs match the story board)
- **Sprint 1 (23-28 Nov):** Day 1 setup + US-03 persona switcher · Day 2 US-01 mock org, US-02 taxonomy ·
  Day 3 US-04 resume → AI skill profile · Day 4 US-05 other sources, US-06 gaps · Day 5 US-07 roadmap,
  US-08 courses · Day 6 US-09 mentor chat + review
- **Sprint 2 (30 Nov-5 Dec):** US-10/11 questionnaire + role fit · US-13/14 readiness + sharing, US-12 tech-stack
  (stretch) · US-15 privacy layer hardening + tests · US-16/17/19 lead + manager views · US-18 org view,
  US-20 transcript (stretch) · US-21 demo story, US-22 deploy to Streamlit Community Cloud
- Never cut US-15 (privacy). Cut US-12, then US-20, if behind.

## Demo story
Priya (Data Engineer, B1) uploads her resume (`data/sample_docs/priya_resume.txt`) → gaps in cloud and
orchestration → roadmap with free courses → mentor chat → role fit: ML Engineer → private readiness score.
Arjun (Team Lead) sees the team cloud gap (4 of 5) but is blocked from Priya's profile. Meera (Manager) sees
rollups; Vikram (VP) sees the org heatmap and the mobility pipeline.
