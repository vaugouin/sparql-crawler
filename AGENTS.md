# AGENTS.md - Agent Guide for Sparql Crawler

## Canary

Start every reply with "Philippe,": no exceptions, including short replies and tool summaries.

Rules and traps for agents. Project overview, scope catalogue, server variables, configuration, Docker build and run: @README.md (canonical). Reference DDL: `doc/sql/*.sql` (`T2S-tables.sql`, `TMDb-tables.sql`, `Wikidata-tables.sql`, `T_WC_SERVER_VARIABLE.sql`), read-only unless the user asks for schema-doc edits; do not duplicate table definitions elsewhere.

Update `README.md` for user-facing behavior, configuration or deployment changes; update this file only when agent workflow or safety context changes.

---

## Related repositories (project ecosystem)

One stage of **Agent BBB** (GitHub `vaugouin`; siblings at `%USERPROFILE%/Code/<repo>` and `github.com/vaugouin/<repo>`, converging on a shared MariaDB with `T_WC_*` tables). Canonical roster and stage map: `%USERPROFILE%/Nestor/projets/t2s-backlog/topics/related-repositories.txt`.

**This repository's role:** acquisition, Wikidata V1 property model. Fetches properties, labels, descriptions and aliases of Wikidata items already linked to TMDb/T2S records into `T_WC_WIKIDATA_*`. Complemented by `sparql-movies-persons` (discovers the QID to TMDb links), superseded for bulk ingestion by the dump-based `wikidata-crawler` (V2). Feeds `tmdb-movie-preprocess` and the Wikidata sections of the web front `t2s-front` (formerly `tmdb-front`).

---

## Code conventions

- Legacy Hungarian notation: `str` strings, `lng` integers, `dbl` floats, `arr` lists/dicts, `int` boolean-like flags.
- Public helpers use the `f_` prefix, private ones `_` (e.g. `_f_t2ssetwikidatacompleted`); Google-style docstrings on public functions.
- Reuse `citizenphil` (`f_getconnection`, `f_sqlupdatearray`, `f_getservervariable` / `f_setservervariable`) rather than ad-hoc connections; progress goes to server variables, not log files.
- **Clock (2026-10-19, DEPLOYMENT-015):** naive `DATETIME` / `DATE` columns hold Europe/Paris time from `datetime.now(cp.paris_tz)`, never bare `datetime.now()` (UTC in the container) nor `NOW()` / `CURDATE()`. A human-read date carries its Paris offset, never a fixed `+02:00`.
- `tmdb_functions.py` is a byte-identical copy of tmdb-crawler's: change it there first, then here, and compare the hashes.
- Keep Markdown, JSON and SQL UTF-8: the data is multilingual and any encoding rewrite introduces mojibake.

---

## sparql-crawler.py scope discovery

Whenever you read or edit `doc/sql/*.sql`, audit for tables with an `ID_WIKIDATA` column that no `intindex` block in `sparql-crawler.py` processes, and **proactively suggest a new scope** (also when you spot one during unrelated work). The crawler is upsert-only with no deletion pass, so a missing scope leaves silent gaps in `T_WC_WIKIDATA_ITEM_PROPERTY`.

1. **Check the fill ratio first**: `SELECT COUNT(*) FROM <table> WHERE ID_WIKIDATA IS NOT NULL AND ID_WIKIDATA <> ''`. Skip always-empty tables unless population is expected.
2. **Prefer the T2S side**: when both `T_WC_TMDB_<X>` and `T_WC_T2S_<X>` carry `ID_WIKIDATA`, the T2S one is usually filled (e.g. `T_WC_TMDB_COLLECTION.ID_WIKIDATA` is always NULL). Verify per pair.
3. **Use the parameterized T2S handler**: add one row to `arrt2sscope` and one entry to `arrwikidatascope`, plus an `f_t2s<entity>setwikidatacompleted` wrapper in `tmdb_functions.py`. Never copy-paste a fresh 90-line block.
4. **Require `TIM_WIKIDATA_COMPLETED`** on the source table (the 30-day filter reads it); if missing, ask the user to run the `ALTER TABLE` shown in README § "Required schema additions", or the SELECT errors out.
5. `ORDER BY IMDB_RATING_WEIGHTED DESC` for movie/serie-linked entities, `POPULARITY DESC` for people-linked ones. Backtick table names that collide with reserved words (`T_WC_T2S_GROUP`).

---

## SQL Object Naming Conventions

- Uppercase snake case (except legacy TMDb genre columns `id`, `name`). Prefixes: `T_WC_*` persistent, `T_WC_T2S_*` Text2SQL read model, `T_WC_TMDB_*` TMDb, `T_WC_WIKIDATA_*` Wikidata (`STG_T_WC_WIKIDATA_*` staging), `T_WC_WIKIPEDIA_*` Wikipedia. Join tables `T_WC_T2S_{PARENT}_{CHILD}`.
- Keys: `ID_{ENTITY}`, `ID_ROW` for generic/join rows, or a table-specific surrogate; foreign keys reuse the referenced key name.
- Suffixes/prefixes: `DAT_*` dates, `TIM_*` timestamps, `IS_*` or legacy integer flags (`DELETED`), `DISPLAY_ORDER`, `*_COUNT`, `*_PATH`, `_FR` / `LANG` for languages, `*_NORM` / `*_KEY` for RapidFuzz columns.
- Index names are mixed legacy style; preserve it: `KEY COLUMN_NAME`, `IDX_*`, `UK_*`, `FK_*`, `ft_*`.

---

**Last Updated**: 2026-10-31
**Current Version**: 1.0.7 

## Backlog (Nestor second-brain)

Backlog for this repo: `C:\Users\vaugo\Nestor\projets\t2s-backlog\repos\sparql-crawler.md` (dashboard: `...\t2s-backlog\index.md`). Tasks are `SPARQL-CRAWLER-NNN`; consult it before implementing. Local paths on Philippe's PC only, they do not resolve on the VPS or cloud agents.
