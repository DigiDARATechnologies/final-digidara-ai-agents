# Job providers

Configuration-driven job collection sources, layered on top of the
existing `job_sources` / `jobs` / `job_ingestion_runs` tables and the
existing `scraper.scrape_source()` dispatch (see `../README.md` for that
base architecture). A provider's only job is: **fetch public data, turn
it into the project's canonical job dict, hand it to the existing
dedup/upsert pipeline.** Nothing here submits applications.

## Tamil Nadu Greenhouse technology registry (current business priority)

`providers.yaml` currently seeds a **verified Tamil Nadu technology/software
company registry** — 17 Chennai-area companies plus 5 newly-discovered
Coimbatore companies, each entry live-checked against the real public
Greenhouse API (and, where the API 404'd, against the hosted
`job-boards.greenhouse.io/<board_id>` career page too) before being
enabled. This is a **seed set, not a claim of complete Tamil Nadu
coverage** — see the "Do not claim completeness" note at the bottom of
this section.

Every company entry carries registry metadata (`district`, `city`,
`state`, `country`, `category`) alongside its `board_id`. This metadata
is **informational only** — it describes the company's known primary
Tamil Nadu presence, and is never used to decide whether a fetched job
counts as a Tamil Nadu job. That decision is made per-job, from the
job's own location text, by `tn_location.py` (below) — a company
registered under Coimbatore can still post a Bangalore or fully-remote
role, and that job must not be miscounted as Tamil Nadu.

### Verified-dead boards (kept, disabled, not deleted)

Five configured board ids were live-checked and found offline — **both**
the public API and the hosted career page return 404, even though each
board id was independently confirmed correct against the company's own
indexed job postings (not a guessed slug):

| Company | Board ID | Checked |
|---|---|---|
| Tekion | `tekion` | 2026-09-03 |
| Integrate | `integrate` | 2026-09-03 |
| Arcadia | `arcadiacareers` | 2026-09-03 |
| Pleo | `pleo` | 2026-09-03 |
| Perch Energy | `perchenergycareers` | 2026-09-03 |

Each stays in `providers.yaml` with `enabled: false` and a dated comment
explaining the check — not deleted, so history/audit is preserved and
re-enabling later (if the board returns) is a one-line edit.

### Pending-validation candidates (never auto-synced)

Two candidates are excluded from sync/collection entirely via
`status: pending_validation` in their `providers.yaml` entry (see
`config_loader.get_pending_validation_companies()`), listed separately by
`GET /api/jobs/admin/providers/greenhouse/pending-companies`:

- **Karat** — the board resolves (`karat`, verified live), but two
  third-party sources disagree on its India office location (Bangalore
  vs. Coimbatore). Not activated until that's resolved; a job's actual
  location, once collected, is never inferred from disputed company-level
  claims.
- **Nexaminds** — evidence of a Greenhouse-sourced Coimbatore posting
  exists, but which Greenhouse board actually belongs to Nexaminds has
  not been confirmed. No `board_id` is configured for it — inventing one
  would violate this project's standing rule against guessing board ids.

## Tamil Nadu location engine (`tn_location.py`)

Provider-independent — has no Greenhouse-specific knowledge, and is
called from `service._clean_job()` so every job from every provider
(current or future) gets the same classification. Given a job's raw
location text, returns three independent values:

- **`location_district`** — the matched Tamil Nadu district (all 32
  covered, with common aliases: `Trichy`/`Tiruchirapalli` →
  `Tiruchirappalli`, `Tuticorin` → `Thoothukudi`, `Tanjore` →
  `Thanjavur`, `Ooty`/`Udhagamandalam` → `The Nilgiris`, ...), or `None`.
- **`location_region`** — `TAMIL_NADU` / `OTHER_INDIA` / `INTERNATIONAL`
  / `UNKNOWN`. A bare `"Remote"` with no place name resolves to
  `UNKNOWN`, deliberately — remote jobs are never assumed to be Tamil
  Nadu (or any other region) without an actual place attached to them.
  `"Remote - Chennai"` still resolves `TAMIL_NADU` via the district match.
- **`location_type`** — `ONSITE` / `HYBRID` / `REMOTE` / `UNKNOWN`.

`GET /api/jobs/admin/tn-coverage` reports the current per-district job
count for every one of the 32 districts, including the ones sitting at
zero — the point is to see where Greenhouse coverage is thin (as of this
seed set: concentrated in Chennai and Coimbatore, zero everywhere else)
so other providers can be prioritized for those districts in a future
milestone, not to make the numbers look more complete than they are.

## GreenhouseProvider

**Purpose:** fetch publicly available job postings from a company's
Greenhouse job board.

**Authentication:** none. This uses Greenhouse's public Job Board API
(`https://boards-api.greenhouse.io/v1/boards/<board_id>/jobs`), the same
no-auth endpoint Greenhouse documents for embedding a company's postings
on a third-party site. No API key is read, stored, or required.

**Configuration:** `providers.yaml`, company name + Greenhouse board id:

```yaml
greenhouse:
  enabled: true
  companies:
    - name: Sagent India
      board_id: sagentindia
      enabled: true
    - name: Appian
      board_id: appian
      enabled: true
    - name: Zenoti
      board_id: zenoti
      enabled: true
```

Override the config file location with `JOBS_PROVIDERS_CONFIG_PATH` if
needed (e.g. a different path per environment). Company names are never
hard-coded in Python — `config_loader.get_greenhouse_companies()` is the
only place that reads this list.

**One provider, any number of companies.** `fetch_and_normalize(board_id,
company_name)` takes the board id and company name as plain arguments —
there is exactly one `GreenhouseProvider` module (`providers/greenhouse.py`),
never `AppianGreenhouseScraper` / `WPPGreenhouseScraper` / etc. Adding
company #24 or #2,400 is a `providers.yaml` edit, not a code change.

**Flow:**

```text
providers.yaml (companies)
        |
        v
sync_greenhouse_sources()      -- upserts one job_sources row per company
        |                          (source_type='greenhouse', pre-authorized:
        |                           this is a documented public API, not an
        |                           arbitrary scraped page). A brand-new
        |                          company starts at status=DISCOVERED; an
        |                          already-known company's health status is
        |                          left untouched (see Source lifecycle
        |                          below) — sync never silently un-fails a
        |                          broken source, only a real attempt does.
        v
run_greenhouse_collection()    -- selects sources with status NOT IN
        |                         (INVALID, DISABLED); loops them; one
        |                         company's failure is logged and skipped,
        |                         the rest continue
        v
scraper.scrape_source()        -- dispatches source_type='greenhouse' to
        |                          providers/greenhouse.py
        v
fetch_company_jobs(board_id)   -- GET the public API, follows meta.next_page
        |                          if Greenhouse returns one, classifies
        |                          every failure (404 / 429 / 5xx / timeout /
        |                          oversized response / malformed JSON) into
        |                          a structured category (see below)
        v
normalize_job(raw, company, board_id)
        |                       -- maps to the canonical dict: source,
        |                          source_job_id, company, title,
        |                          description, location, department,
        |                          employment_type, workplace_type,
        |                          posted_at/updated_at, job_url,
        |                          application_url. Fields Greenhouse does
        |                          not provide are left empty, never guessed.
        v
service.process_run()          -- the EXISTING dedup/upsert logic (content
                                   hash + (source_id, external_id) unique
                                   keys), unchanged. New jobs land as
                                   status='active' automatically for candidate matching,
                                   same as every other source type. Also
                                   updates the source's lifecycle status,
                                   error_category, last_attempted_at, and
                                   last_success_at.
```

Running collection twice is a no-op the second time (existing unique
constraints turn the second pass into zero-row updates instead of new
rows) — verified with a real board fetched twice in a row, 0 inserted /
N updated on the second pass.

`application_url` is Greenhouse's `absolute_url` — the job's own posting
page. Students click through to apply there themselves; nothing in this
module submits an application, drives a browser, or automates a form.

### Source lifecycle

Every `job_sources` row (any `source_type`, not just Greenhouse) carries a
`status`, set by `service.process_run()` after each attempt:

| Status | Meaning | Included in the next automatic run? |
|---|---|---|
| `discovered` | Just synced from config, never attempted | Yes |
| `validating` | An attempt is in progress right now | n/a (transient) |
| `active` | This source has at least one job stored, regardless of what this specific run fetched | Yes |
| `empty_board` | Last attempt succeeded, the provider genuinely has zero published jobs, and nothing is stored | Yes — not a failure, just nothing published |
| `no_matching_jobs` | Last attempt succeeded, the provider has jobs, but none have ever passed the location/entry-level filters | Yes — not a failure, filters may match a future posting |
| `temporarily_failed` | Last attempt hit a transient error (timeout, 403, rate limit, 5xx, oversized response, malformed JSON) | Yes — may well succeed next time |
| `invalid` | Last attempt hit a permanent error (board not found, malformed board id) | **No** — retrying a dead board every run forever is pointless |
| `disabled` | Removed from `providers.yaml`, or turned off by an admin | No |
| `pending_validation` | A candidate company/board that hasn't been confirmed yet (see Karat/Nexaminds above) | Never synced as a `job_sources` row in the first place |

Status reflects what is actually **stored** for that source, not just
this run's outcome: a source with jobs on file from an earlier run stays
`active` even if this particular run's fetch came back empty (a board can
go temporarily quiet without its previously-collected postings becoming
invalid). Only when nothing is stored at all does the distinction
between `empty_board` and `no_matching_jobs` matter, and that distinction
uses the provider's raw (pre-filter) count — `last_fetched_count` on the
`job_sources` row, and `fetched_job_count` in the
`/providers/greenhouse/companies` API response — which Greenhouse's
own location/entry-level filters (applied before `process_run()` ever
sees the list) never overwrite or hide. Check the provider's per-run log
line too (e.g. `"9 kept, 132 outside target locations, 20 filtered as
senior-level"`) for the filter breakdown.

`error_category` records *why* on failure (`board_not_found`,
`forbidden`, `rate_limited`, `server_error`, `unexpected_response`,
`response_size_limit`, `malformed_response`, `timeout`, `network_error`,
`invalid_configuration`), alongside `last_error` (the human-readable
message), `last_attempted_at` and `last_validated_at` (both updated on
every attempt), and `last_success_at` (successes only) — so "is this
source healthy" and "when did it last actually work" are two different,
both-answerable questions. `consecutive_failures` counts unbroken failed
attempts and resets to 0 on any success, including `empty_board` and
`no_matching_jobs`.

`GET /api/jobs/admin/providers/greenhouse/summary` returns the aggregate
across every configured company — `total_jobs`, `tamil_nadu`,
`other_india`, `international`, `unknown` — computed by summing the exact
per-company rows `/providers/greenhouse/companies` returns, so the two
endpoints can never disagree. This is deliberately narrower than
`/admin/tn-coverage`, which counts every discovered job across every
source and status (including disabled sources' historical jobs) for a
broader coverage picture; use the summary endpoint when you need numbers
that reconcile with the visible per-company table.

**An INVALID source is not deleted, and not silently retried forever.**
It stays in the table (and in the UI) with its error visible, for audit
and so it doesn't quietly vanish. To force one more attempt regardless of
current status — after fixing a board id, or if you believe a Greenhouse
outage has cleared —:

```text
POST /api/jobs/admin/providers/greenhouse/sources/<source_id>/revalidate
```

This reuses the exact same `queue_source_run`/`process_run` pipeline as a
normal run, so success/failure updates status the same way a scheduled
run would. The admin UI's Scraper Sources tab shows a **Revalidate**
button automatically on any Greenhouse source whose status is `invalid`
or `temporarily_failed`.

Classification is provider-agnostic: `process_run()` reads `.category` /
`.permanent` off whatever exception a provider raises (duck-typed, not a
Greenhouse-specific `isinstance` check), so a future provider gets the
same lifecycle tracking for free just by setting those two attributes on
its own error class.

### Handling large boards without a blanket size increase

A handful of large companies (many jobs, long HTML descriptions with
`content=true`) can exceed a byte ceiling. Two provider-specific choices,
deliberately not a single global setting bumped for every source type:

1. **`GREENHOUSE_MAX_RESPONSE_BYTES`** (`JOBS_GREENHOUSE_MAX_RESPONSE_BYTES`
   env var, default 15MB) — separate from the generic scraper's
   `SCRAPER_MAX_BYTES` (5MB, used by the json_ld/html_cards/rss source
   types). Greenhouse's API is a trusted, structured JSON endpoint, not an
   arbitrary scraped page, so it gets its own, more generous ceiling
   rather than raising the limit for every provider.
2. **Graceful fallback**: if a board still exceeds that limit,
   `fetch_company_jobs()` retries once *without* `content=true` — a much
   smaller, metadata-only payload — instead of failing outright or
   dropping descriptions for every other company. Only that one
   oversized board loses its descriptions; everything else is unaffected.
   If even the metadata-only response is too large, the fetch raises
   (category `response_size_limit`, transient — retried next run) rather
   than looping or truncating silently.

### Running it

From `backend` with the virtual environment active:

```powershell
# One-off: reconcile job_sources with providers.yaml, no fetching
python -m jobs.worker --sync-providers

# Sync + fetch every enabled company once
python -m jobs.worker --run-greenhouse
```

Or, for an already-running backend, an authenticated admin can enqueue the
same per-source work over HTTP:

```text
POST /api/jobs/admin/providers/greenhouse/sync
POST /api/jobs/admin/providers/greenhouse/run
GET  /api/jobs/admin/providers/greenhouse/companies
POST /api/jobs/admin/providers/greenhouse/sources/<source_id>/revalidate
```

`POST .../greenhouse/run` returns `202 Accepted` immediately after adding
eligible sources to `job_ingestion_runs`; it does not fetch Greenhouse in
the web request. The continuous `job_agent.worker` process performs the
network and database work. Duplicate queued/running runs for the same
source are suppressed, and the admin Sources tab polls the run table for
progress and errors. The explicit one-off `--run-greenhouse` CLI remains a
synchronous worker-side maintenance command.

Schedule `--run-greenhouse` with the same process manager / cron that
would run any other periodic job (this milestone does not add its own
scheduler; it reuses the existing worker entrypoint style).

### Tests

```powershell
python -m unittest discover -s jobs\tests -p "test_greenhouse_*.py" -v
python -m unittest discover -s jobs\tests -p "test_source_lifecycle.py" -v
```

- `test_greenhouse_config.py` — providers.yaml loading: enabled/disabled
  provider, multiple companies, disabled company skipped, missing
  board_id skipped, missing config file.
- `test_greenhouse_provider.py` — HTTP fetch (mocked): success, multiple
  companies, empty board, 404, 429, 500, an unexpected status code,
  timeout, connection error, malformed JSON, pagination, the oversized
  -> metadata-only fallback (and the case where even that is too large);
  every failure's `.category`/`.permanent` classification; and
  normalization field-mapping.
- `test_greenhouse_integration.py` — full config -> mocked API ->
  normalize -> dedupe -> real local database flow, plus a three-company
  run where the middle company fails and the other two still succeed.
  Skipped automatically if no MySQL database is reachable.
- `test_source_lifecycle.py` — status transitions from real `process_run()`
  calls (success -> ACTIVE, board-not-found -> INVALID, timeout/5xx ->
  TEMPORARILY_FAILED, a temporarily-failed source succeeding on retry ->
  back to ACTIVE); INVALID excluded from automatic selection while
  TEMPORARILY_FAILED and DISCOVERED are still included; DISABLED excluded;
  `revalidate_greenhouse_source()` forcing a re-attempt regardless of
  status, both when it succeeds and when the board is still broken;
  `sync_greenhouse_sources()` never resets an INVALID source back to
  healthy, correctly marks a company removed from config as DISABLED,
  reactivates a DISABLED company that returns to config, and is
  idempotent. Also skipped automatically if MySQL is unreachable. Every
  test that calls the real `sync_greenhouse_sources()` builds its mocked
  config from the actual configured companies (via
  `get_greenhouse_companies()`) plus its own synthetic test board, never a
  reduced or empty list — that function reconciles the *entire* shared
  `job_sources` table, so a naively empty mocked config would disable
  every real company's row as a side effect, not just the row the test
  created.

### Ready for future automatic company/ATS discovery (not built yet)

This milestone does **not** implement automatic discovery ("type a
company name, find their careers page, detect the ATS, find the board
id, validate it, create the source"). It deliberately keeps the pieces
that flow would need already in place, so building it later is additive
rather than a rearchitecture:

- **Source identity is already a `{provider, identifier, company_name}`
  triple**, not something baked into code: `source_type` is the provider,
  `parser_config.board_id` is the identifier, `parser_config.company_name`
  is the display name. A discovery engine's end state — "create a source
  record" — is just one more caller of the same `job_sources` upsert
  `sync_greenhouse_sources()` already does, keyed the same way
  (`greenhouse:<board_id>`).
- **`status='discovered'`** already exists as the lifecycle's starting
  point, named for exactly this: a discovery flow would create a row at
  `discovered`, and the very next scheduled run (or an explicit
  revalidate) naturally transitions it to `validating` -> `active` /
  `invalid` — the "validate the board" step a discovery flow needs is
  already `process_run()`, not new code.
- **Per-source `status`/`error_category`/timestamps** give a discovery
  flow (or the admin reviewing its output) an immediate, structured
  answer to "did the board id I found actually work" without adding
  another tracking mechanism.
- **The provider function signature is already discovery-shaped**:
  `fetch_and_normalize(board_id, company_name)` takes exactly the two
  pieces of information a discovery flow would produce (an identifier and
  a display name) and nothing Greenhouse-account-specific.

What discovery would still need to add later — not present now — is the
company-name -> careers-page -> ATS-detection -> board-id-extraction
logic itself (an external lookup/heuristic problem, unrelated to how
sources are stored or executed), and, if it should run unattended, a
review queue so a newly `discovered` source is confirmed before it's
treated as trusted.

## Apify job boards (7 live; LinkedIn pending)

Live: Naukri, Foundit, Hirist, Instahyre, Internshala, Indeed, Glassdoor.
Pending an actor id: LinkedIn.

Each job board scraped through Apify is one entry under `apify.actors` in
`providers.yaml`: `{platform, actor_id, enabled}`. `platform` is the
dispatch key `providers/apify.py`'s `normalize_job()` uses to pick that
actor's field mapping — every actor on Apify returns different field
names, so there is one mapping function per platform in `_NORMALIZERS`
(all delegating to a shared `_normalize_generic_job()` helper with
platform-specific candidate field names via `extra_*` arguments, rather
than seven near-duplicate functions).

**Unlike Greenhouse, no Apify platform is ever collected automatically.**
Each is queued manually, one platform at a time, from the admin panel's
Sources tab ("Queue run" next to that platform), or via
`POST /api/jobs/admin/providers/apify/run` with `{"platform": "naukri"}`
in the body (omit `platform` to run every enabled one). `GET
.../providers/apify/actors` lists every configured platform with its
configured/not-configured state and last-run health, for that same tab.
The POST returns `202` after queueing; only `job_agent.worker` calls Apify.

### Naukri — `crawloop/naukri-jobs-scraper`

Wired and enabled. `_normalize_naukri_job()` in `providers/apify.py` is a
**best-effort field mapping, not yet verified against a real run** —
this actor's exact dataset shape hasn't been confirmed, so every field
tries several plausible candidate key names (e.g. `title`/`jobTitle`, or
`companyName`/`company`) and simply omits what it can't find rather than
guessing one name with false confidence. After the first real "Run now"
click, check that source's row in `job_ingestion_runs` (fetched/rejected
counts) and `job_sources.last_error` — if `rejected` is high or nothing
was inserted, the field names need adjusting to match what actually came
back.

### Foundit, Hirist — `crawloop/foundit-jobs-scraper`, `crawloop/hirist-jobs-scraper`

Wired and enabled. Same actor author as Naukri (crawloop), so their
candidate field names mirror Naukri's — but **unverified against a real
run**, same as every platform below. Check `job_ingestion_runs`
(fetched/rejected counts) and `job_sources.last_error` after each
platform's first "Run now" click.

### Instahyre, Internshala, Indeed, Glassdoor

- **Instahyre** (`parsebird/instahyre-jobs-scraper`) and **Indeed**
  (`solidscrape/indeed-jobs-scraper`) — different actor authors than the
  crawloop-based platforms above, so their field names may diverge more.
- **Internshala** (`hipersoft/internshala-scraper`) — internship listings,
  so `_normalize_internshala_job()` also tries `stipend` (not just
  `salary`) and `internship_name` (not just `title`).
- **Glassdoor** (`simpleapi/glassdoor-jobs-scraper`).

All four: wired, enabled, and carry the same **unverified, best-effort**
caveat as every platform above — check the same run/error signals after
each one's first "Run now" click, and tighten that platform's `extra_*`
candidate list in `providers/apify.py` if fields come back empty.

### LinkedIn

Configured in `providers.yaml` but `enabled: false` — needs an actor id
and one real sample dataset item before `normalize_job()` can be written
for it (same reasoning as every platform above, just not attempted yet
without a real sample). Add a `_normalize_linkedin_job()` function (or a
one-line `_normalize_generic_job()` wrapper, same as the others),
register it in `_NORMALIZERS`, and flip its `providers.yaml` entry to
`enabled: true`.

To activate a brand-new platform from scratch:

1. Set the `APIFY_API_TOKEN` environment variable (never commit it to
   `providers.yaml` or anywhere else in the repo).
2. Add `{platform, actor_id, enabled: true}` under `apify.actors` in
   `providers.yaml`.
3. Implement `_normalize_<platform>_job()` in `providers/apify.py` and add
   it to `_NORMALIZERS`.

Until a platform has both a configured actor id and a `_NORMALIZERS`
entry, running it fails clearly (a normal failed run with a specific
message) rather than guessing at its output shape.
