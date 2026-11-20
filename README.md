# Career Growth Agent (pitch build)

An AI career agent that coaches each employee **privately** and gives every level above them an
**aggregated, privacy-safe** view of their team's growth. Everything here is free to run.

## 1. Tools you need (all free)

| What | Use | Why |
| --- | --- | --- |
| Code editor | **VS Code** on your laptop, or **GitHub Codespaces** (VS Code in the browser, free monthly hours) | The app is a multi-file Python project; a notebook can't run it well |
| Notebooks | **Google Colab** | Explore the dataset, test prompts, measure AI accuracy (`notebooks/`) |
| Python | **Python 3.11+** and **uv** (package manager) | `uv` installs everything in one command |
| Version control | **Git + GitHub** (free) | Back up daily; needed for Codespaces and for free deployment |
| AI model | **Google AI Studio** free key (Gemini Flash) | Primary model, no card needed |
| Backup AI model | **Groq** free key, or **Ollama** (runs models on your laptop) | When Gemini's daily free quota runs out |
| Hosting | **Streamlit Community Cloud** | Free public URL for the demo |

## 2. Install (about 10 minutes)

```bash
# 1. install uv (macOS/Linux; for Windows see https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. inside this folder: create the environment and install all packages
uv sync

# 3. add your free keys
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
#    then paste GEMINI_API_KEY (from aistudio.google.com) and, optionally, GROQ_API_KEY

# 4. load the demo company and start the app
uv run python scripts/seed.py
uv run streamlit run app.py
```

Open http://localhost:8501, pick a persona in the sidebar (Priya → Arjun → Meera → Vikram) and walk the demo.

Checks: `uv run pytest` (privacy, aggregates, scores, recommendations) · `uv run python scripts/check_links.py` (course links).

## 3. The dataset (synthetic, made for this project)

Real employee data is private, so the app runs on **Nimbus Tech**, a synthetic company:
27 people, 4 teams (Data Engineering, Cloud Platform, Frontend, ML), bands B1-B4.

- `core/seed.py` builds it into the SQLite database (fixed random seed, so every demo is identical).
- `uv run python scripts/export_dataset.py` writes it to `data/synthetic/` as CSV files plus a
  resume and a review for every person (`documents/`). `skills_ground_truth.csv` is the answer key
  the documents were generated from, so you can measure how accurately the AI reads them.
- `data/sample_docs/priya_resume.txt` is the resume to upload live in the demo.
- `data/taxonomy.yaml`: roles, skills, mandatory / good-to-have / org-wide levels.
- `data/catalog.yaml`: free courses from **Microsoft Learn, freeCodeCamp and Kaggle Learn**.

Public data for testing prompts only: the Kaggle *Resume Dataset* (`UpdatedResumeDataSet.csv`,
962 resumes in 25 categories), loaded inside `notebooks/01_extraction_playground.ipynb`.

## 4. Notebooks (open in Google Colab: File → Upload notebook)

1. `01_extraction_playground.ipynb`: try the skill-extraction prompt on public resumes.
2. `02_synthetic_dataset_and_eval.ipynb`: upload `synthetic.zip`, see team coverage, and score the
   extractor against the answer key (exact-level and within-one-level accuracy).

## 5. Project map

```
app.py               navigation + persona switcher
views/               my_growth, upload, roadmap, mentor (chatbot), my_team, org
core/access.py       privacy layer: the only door to personal data
core/aggregate.py    team/org metrics, hidden for groups under 5 people
core/llm.py          one client for Gemini / Groq / Ollama, JSON validation, caching
core/extract.py      documents → skill profile        core/gaps.py       gap analysis
core/readiness.py    promotion readiness score        core/recommend.py  free course picks
core/rolefit.py      role-fit suggestion              core/mentor.py     chatbot prompt + questionnaire
core/seed.py, core/synthetic.py   the synthetic company and its documents
```

Privacy note: free AI tiers may use prompts to improve their products. Send only synthetic data.