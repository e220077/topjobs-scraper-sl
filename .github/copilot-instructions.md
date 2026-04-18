# Copilot Instructions for `topjobs_scraper`

## Build, test, and lint commands

This repository currently has **no configured build/lint toolchain** (no linter config, no formatter config), but it now includes a small `unittest` suite.

Operational commands used by the project:

```bash
# Match CI runtime
python3.9 -m pip install --upgrade pip
pip install requests beautifulsoup4 psycopg2-binary pytesseract Pillow google-generativeai

# Initialize DB schema
python db_init.py

# Run scraper + auto-apply flow
python scraper.py

# Backfill missing emails/descriptions for existing DB rows
python repair_database.py

# Run all tests
./venv/bin/python -m unittest discover -s tests -v

# Run a single test module
./venv/bin/python -m unittest tests.test_scraper_analyze -v
```

GitHub Actions workflow:

```bash
# Defined in .github/workflows/cloud_scraper.yml
# Scheduled daily at 03:00 UTC and manual dispatch
python scraper.py
```

## High-level architecture

The project is a script-based pipeline centered on one shared PostgreSQL table (`job_listings`):

1. `db_init.py` creates/updates the `job_listings` table schema in Supabase/PostgreSQL.
2. `scraper.py` is the orchestrator:
   - Scrapes TopJobs category pages (`SDQ`, `IT`, `HNS`).
   - Parses each row’s `onclick` payload into a `JobAdvertismentServlet` URL.
   - Fetches each job page once to extract visible text, candidate email(s), and vacancy image URL.
   - Performs regex-based deterministic matching first (target skills + role keywords, forbidden-skill filter).
   - Uses Gemini as fallback when page data is insufficient (primarily for image-only ads or missing email).
   - Upserts matched jobs into `job_listings`.
   - Auto-applies by email for rows where `contact_email IS NOT NULL` and `application_sent = FALSE`, then marks `application_sent = TRUE`.
3. `repair_database.py` repairs previously scraped rows missing contact details by re-normalizing links, extracting page emails, and using Gemini only as needed.
4. `.github/workflows/cloud_scraper.yml` runs the scraper in CI on a schedule/manual trigger.

## Key codebase conventions

- **Canonical job URL form:** use TopJobs employer servlet links (`https://www.topjobs.lk/employer/JobAdvertismentServlet?...`). Both scrape and repair flows normalize toward this form.
- **Record identity and merge behavior:** `job_link` is the unique key. Inserts use `ON CONFLICT (job_link)` and only refresh `contact_email`/`job_description` when the existing row has `contact_email IS NULL`.
- **Two-stage extraction:** page HTML email extraction is preferred; Gemini email/skills extraction is fallback and merged with page data.
- **Matching semantics:** matching uses compiled regex patterns (skills + role hints) and word boundaries to avoid naive substring matches (e.g., `Java` from `JavaScript`).
- **Filter-first persistence:** rows are only saved when they pass forbidden-title/forbidden-skill checks and match at least one target skill/role pattern.
- **Email application gating:** only records with discovered emails and `application_sent = FALSE` are eligible for auto-apply.
- **Environment-driven runtime:** scripts require environment variables (`DATABASE_URL`, `GEMINI_API_KEY`, `EMAIL_SENDER`, `EMAIL_PASSWORD`); cloud execution expects these as GitHub Actions secrets.
