# AGENTS.md - Agent Guide for Sparql Crawler

This file gives you the agentic context you need to work on this codebase safely. For project overview, features, install / deploy steps and human-facing security / performance / troubleshooting material, read @README.md — that file is canonical and not duplicated here.

This is the single canonical guide for autonomous coding agents in this repository. Assistant-specific files such as @CLAUDE.md, and any future tool-specific guide such as `GEMINI.md`, should only point here and should not duplicate repository instructions.

Deeper specs live in their own files:
- @doc/sql/*.sql — reference DDL for the database schema; treat these files as read-only unless the user explicitly asks you to edit schema documentation

- For any project update, keep documentation aligned:
  - Update `README.md` for user-facing behavior, configuration, setup, deployment, troubleshooting, or verification changes.
  - Update this file only when agent workflow or safety context changes.

---

## Related repositories (project ecosystem)

`sparql-crawler` is one stage of **Agent BBB**, a multi-repository movie/TV database system owned by GitHub user `vaugouin`. All sibling repos live under `%USERPROFILE%/Code/<repo>` and at `github.com/vaugouin/<repo>`; they are interdependent stages of one pipeline that converges on a shared MySQL/MariaDB database (`T_WC_*` tables) and a ChromaDB vector store. The canonical roster of sibling repositories is kept in `%USERPROFILE%/Nestor/projets/t2s-backlog/topics/related-repositories.txt` (documentation repo `Nestor`, outside `Code/`).

Pipeline stages:
- **Infrastructure** — `python` (shared crawler base image), `chromadb` (vector service), `reverseproxy` (NGINX TLS ingress), `chromadb-security-test` (firewall validation).
- **Acquisition** — `tmdb-crawler`, `imdb-crawler`, `sparql-crawler`, `sparql-movies-persons`, `wikidata-crawler`, `wikipedia-crawler`, `selenium-tmdb`, `download-images`, `sqlite-plex-to-tmdb`, `movieparadise`.
- **Preprocessing → `T_WC_T2S_*`** — `tmdb-movie-preprocess`, `tmdb-person-preprocess`, `keywords-processing`.
- **Semantic index & name resolution** — `embedding-update`, `embedding-query`, `rapidfuzz_query`.
- **Serving** — `fastapi-text2sql` (NL→SQL API + MCP server), `voice-agent`, `tmdb-front` (PHP web front-end).
- **Evaluation** — `eval-text2sql`, `extract-movie-questions`.
- **Maintenance & tooling** — `plex-duplicates`, `subtitle-translate`, `powershell`, `playwright-test`.
- **Monitoring & observability** — `data-monitoring`.

**This repository's role:** Acquisition stage (Wikidata, V1 property model). Crawls Wikidata items already linked to TMDb records via SPARQL to fetch their properties, labels, descriptions, and aliases into the `T_WC_WIKIDATA_*` tables. It is complemented by `sparql-movies-persons` (which discovers the QID↔TMDb links) and superseded for bulk ingestion by the dump-based `wikidata-crawler` (V2). Output feeds `tmdb-movie-preprocess` and the Wikidata sections rendered by `tmdb-front`.

---

## Where things live (file → role)

Edit at the right layer; the architecture is intentionally split.

## Code conventions

- **Hungarian notation** for variables (legacy style):
  - `str` — strings (`strtablename`, `strapiversion`)
  - `lng` — integers (`lngpage`, `lngrowsperpage`)
  - `dbl` — floats (`dblavailableram`)
  - `arr` — lists / arrays
  - `int` — boolean-like flags (`intcleanupenabled`, `intentity`)
- **Function naming**: public pipeline entry points use `f_` (`f_text2sql`, `f_entity_extraction`, `f_resolve_complex_question`, `f_answer_single_value`, `f_hello_world`); private helpers use `_` (`_call_chat_llm`, `_normalize_llm_model`).
- **Docstrings**: Google-style on public functions.
- **Error handling**: broad try/except with console logging; surface failures via the `error` response field and the `messages` trace. Database execution errors are not returned directly to clients — they go through the complex-question retry path when enabled.
- **JSON serialization**: use `logs.decimal_serializer()` for `Decimal` and `datetime`.

---

## Database Schema Sources

Full DDL lives under [doc/sql/](doc/sql/); do not duplicate table definitions here. Treat these files as reference-only unless the user explicitly asks for schema-doc edits.

- [doc/sql/T2S-tables.sql](doc/sql/T2S-tables.sql) — canonical Text2SQL read-model tables used by prompts, API detail endpoints, cache, and evaluation tables.
- [doc/sql/TMDb-tables.sql](doc/sql/TMDb-tables.sql) — source TMDb tables and reference tables.
- [doc/sql/Wikidata-tables.sql](doc/sql/Wikipedia-tables.sql) — Wikidata tables.

---

## sparql-crawler.py scope discovery

The crawler in [sparql-crawler.py](sparql-crawler.py) is driven by `arrwikidatascope` near the top of the main loop. Each scope picks `ID_WIKIDATA` values from a parent table, fans them out to WDQS via batched `VALUES ?item { ... }` queries, and upserts `(ID_WIKIDATA, ID_PROPERTY, ID_ITEM)` triples into `T_WC_WIKIDATA_ITEM_PROPERTY`.

Whenever you read or edit `doc/sql/*.sql`, audit for tables with an `ID_WIKIDATA` column that the crawler does not yet process — and proactively suggest a new scope:

1. **List candidates.** Any table with an `ID_WIKIDATA` column that is not already a source for an `intindex` block in [sparql-crawler.py](sparql-crawler.py) is a candidate.
2. **Check fill ratio.** Before proposing, run `SELECT COUNT(*) FROM <table> WHERE ID_WIKIDATA IS NOT NULL AND ID_WIKIDATA <> ''`. Skip tables that are always empty unless there's reason to expect future population.
3. **Prefer the T2S side.** When both `T_WC_TMDB_<X>` and `T_WC_T2S_<X>` carry `ID_WIKIDATA`, the T2S side is usually the authoritative one because the text2SQL data-prep pipeline backfills `ID_WIKIDATA` there. The TMDb side is often empty (e.g. `T_WC_TMDB_COLLECTION.ID_WIKIDATA` is always NULL while `T_WC_T2S_COLLECTION.ID_WIKIDATA` is well-populated). Verify per pair with the fill-ratio query before choosing the source.
4. **Use the parameterized T2S handler.** Scopes 118–127 share one block keyed by `arrt2sscope` near scope 117 in [sparql-crawler.py](sparql-crawler.py). For a new T2S table, add one row to that dict (table, PK column, label column, ORDER BY column, helper, server-variable suffix) and one entry to `arrwikidatascope`. Do not copy-paste a fresh 90-line block.
5. **Add the helper.** Each scope needs an `f_t2s<entity>setwikidatacompleted(lngid)` wrapper in [tmdb_functions.py](tmdb_functions.py) calling the shared `_f_t2ssetwikidatacompleted` helper. Helpers exist for symmetry with `f_tmdb*setwikidatacompleted` so call sites read uniformly.
6. **Require `TIM_WIKIDATA_COMPLETED`.** The 30-day eligibility filter relies on this column. If the candidate table lacks it, ask the user to run `ALTER TABLE <table> ADD COLUMN TIM_WIKIDATA_COMPLETED datetime DEFAULT NULL, ADD KEY (TIM_WIKIDATA_COMPLETED);` before the scope can do useful work — the SELECT will otherwise error out.
7. **`ORDER BY` choice.** Use `IMDB_RATING_WEIGHTED DESC` when present (movie/serie-linked entities), `POPULARITY DESC` for people-linked entities (deaths, groups), so the crawler hits the highest-signal rows first within the per-run LIMIT.
8. **Bare-table SQL safety.** Some T2S table names collide with MySQL reserved words (e.g. `T_WC_T2S_GROUP`). Wrap table names in backticks in the SELECT to stay portable.

If you discover a candidate table while doing unrelated work, mention it in your reply rather than silently moving on. The crawler is upsert-only and has no deletion pass, so missing scopes leave silent gaps in `T_WC_WIKIDATA_ITEM_PROPERTY` that are hard to spot later.

---

## SQL Object Naming Conventions

- SQL table and column names are uppercase snake case, except legacy imported TMDb genre columns such as `id` and `name`.
- Persistent tables use `T_WC_*`.
- Text2SQL read-model tables use `T_WC_T2S_*`.
- TMDb source/reference tables use `T_WC_TMDB_*`.
- Wikidata tables use `T_WC_WIKIDATA_*`; staging tables use `STG_T_WC_WIKIDATA_*`.
- Wikipedia tables use `T_WC_WIKIPEDIA_*`.
- Join tables usually follow `T_WC_T2S_{PARENT}_{CHILD}`, for example `T_WC_T2S_MOVIE_GENRE`, `T_WC_T2S_PERSON_MOVIE`.
- Primary keys are usually `ID_{ENTITY}` for entity tables, `ID_ROW` for generic/join rows, or a table-specific surrogate such as `ID_T2S_PERSON_MOVIE`.
- Foreign keys reuse the referenced primary-key name, for example `ID_MOVIE`, `ID_PERSON`, `ID_GENRE`.
- Date columns use `DAT_*`; datetime/timestamp columns use `TIM_*`.
- Boolean-like flags use `IS_*` or legacy integer flags such as `DELETED`.
- Ordering uses `DISPLAY_ORDER`.
- Aggregate counters use `*_COUNT`.
- Media paths use `*_PATH`.
- Language-specific labels/titles often use suffixes such as `_FR`; generic language rows use `LANG`.
- RapidFuzz/generated search columns use `*_NORM` and `*_KEY`; popularity tie-breakers commonly use `POPULARITY`.
- Index names are mixed legacy style. Preserve existing style: simple `KEY COLUMN_NAME`, `IDX_*` for indexes, `UK_*` for unique keys, `FK_*` for foreign keys, and `ft_*` for FULLTEXT indexes.

---

## Encoding

Keep Markdown, prompt files, JSON config, and logs UTF-8. These files contain non-ASCII names and multilingual examples. Avoid editor or terminal operations that rewrite them with mojibake.

---

## Build & deployment (Docker)

Built and run as a Docker container via the repo's `Dockerfile` (base `python:3.10.5-slim-buster`). The image installs `requirements.txt`, copies the repo into `/app`, and runs the crawler as `CMD ["python", "./sparql-crawler.py"]` — a one-shot batch job, no exposed ports or volumes. Secrets stay out of the image: `.env` and `citizenphilsecrets.py` are excluded by `.dockerignore` and supplied at runtime (e.g. `docker run --env-file`).

---

**Last Updated**: 2026-06-03
**Current Version**: 1.0.0 

## Backlog (Nestor second-brain)

The prioritized, agent-ready implementation backlog for this repo lives in the **Nestor**
knowledge repo (a separate repo, not cloned alongside this one):

- This repo: `C:\Users\vaugo\Nestor\projets\t2s-backlog\repos\sparql-crawler.md`
- Cross-repo dashboard: `C:\Users\vaugo\Nestor\projets\t2s-backlog\index.md`

Consult it before implementing: tasks are `SPARQL-CRAWLER-NNN` with status (done / in-progress /
todo), priority, and quick-wins. NOTE: these are local paths on Philippe's PC and do not
resolve on the VPS or on cloud agents (claude.ai/code).
