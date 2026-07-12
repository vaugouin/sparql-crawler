# Sparql Crawler

Crawler that enriches a TMDb-based relational database with data pulled from Wikidata via SPARQL. The single entry point [sparql-crawler.py](sparql-crawler.py) connects to MySQL through [citizenphil.py](citizenphil.py), iterates a configurable list of processes (each identified by a numeric scope), runs SPARQL queries against `https://query.wikidata.org/sparql`, and upserts the results into the `T_WC_WIKIDATA_*` tables.

For agent / contributor conventions see [AGENTS.md](AGENTS.md).

---

## What the crawler does

On each run the script walks an ordered `arrwikidatascope` dictionary and executes the selected processes one after another. The current default scope (see [sparql-crawler.py:59](sparql-crawler.py#L59)) is:

```python
arrwikidatascope = {100: 'property', 109: 'item add', 112: 'move item to person',
                    115: 'person properties VIP', 105: 'person properties',
                    104: 'movie properties', 114: 'serie properties',
                    116: 'season properties', 117: 'episode properties',
                    118: 't2s collection properties', 119: 't2s character properties',
                    120: 't2s award properties', 121: 't2s nomination properties',
                    122: 't2s topic properties', 123: 't2s technical properties',
                    124: 't2s group properties', 125: 't2s movement properties',
                    126: 't2s list properties', 127: 't2s death properties'}
```

An `if strnow.startswith("YYYY-MM-DD"):` override immediately below the default ([sparql-crawler.py:60-61](sparql-crawler.py#L60-L61)) lets you swap or reorder the scope for a specific run date — useful when seeding a new table or prioritising a backfill ahead of the regular cadence.

### Process catalogue

| Scope | Label | Source table → Target table | What it does |
|------:|-------|-----------------------------|--------------|
| 100 | property | Wikidata properties → `T_WC_WIKIDATA_PROPERTY` | Pulls every Wikidata property (`?property a wikibase:Property`) with its `en` and `fr` label and description in a single POST query (explicit `OPTIONAL { … FILTER(LANG(…) = "xx") }` clauses), writing `LABEL` / `DESCRIPTION` / `LABEL_FR` / `DESCRIPTION_FR`. Runs at most once per Paris-day: the date of the last successful run is stored in `strsparqlcrawlerpropertieslastrundate` and the scope is skipped on subsequent runs the same day. |
| 103 | serie | (legacy, currently a no-op stub) | Year-bucketed series crawl; loop is short-circuited by `intencore = False`. |
| 104 | movie properties | `T_WC_TMDB_MOVIE` × `T_WC_IMDB_MOVIE_RATING_IMPORT` → `T_WC_WIKIDATA_ITEM_PROPERTY` | For up to 1000 TMDb movies (ranked by IMDb rating, refreshed > 30 days ago) downloads all `?property / ?value` pairs and marks the movie via `tf.f_tmdbmoviesetwikidatacompleted`. Batches Wikidata ids into POST queries of 50 with a `VALUES ?item { … }` clause. |
| 105 | person properties | `T_WC_TMDB_PERSON` → `T_WC_WIKIDATA_ITEM_PROPERTY` | Same shape as 104. Pulls up to 2000 persons ranked by `POPULARITY`, refreshed > 30 days ago, and POSTs them to WDQS in batches of 25. Calls `tf.f_tmdbpersonsetwikidatacompleted`. |
| 106 | movie aliases | `T_WC_TMDB_MOVIE` × `T_WC_WIKIDATA_MOVIE_V1` → `T_WC_WIKIDATA_MOVIE_V1.ALIASES` | Fills the `ALIASES` pipe-delimited column for movies whose value is NULL, using `skos:altLabel` in `en` / `fr`. |
| 107 | person aliases | `T_WC_TMDB_PERSON` × `T_WC_WIKIDATA_PERSON_V1` → `T_WC_WIKIDATA_PERSON_V1.ALIASES` | Same as 106 but for persons; limit 1000 per run. |
| 109 | item add | `T_WC_WIKIDATA_ITEM_PROPERTY` → `T_WC_WIKIDATA_ITEM_V1` | Resolves up to 5000 Wikidata `?item` ids that don't yet have a label/title in `_ITEM_V1`, `_PERSON_V1`, `_MOVIE_V1`, or `_SERIE_V1`. Uses **batched** POST queries (`VALUES ?item { wd:Q1 wd:Q2 ... }`) to fetch `label / description / altLabel / P31 (instanceOf)` in both `en` and `fr`. The outer slice (cursor advance) is 500 ids; inside the lang loop it sub-batches per language — EN runs as 200-id POSTs (50-language fallback in the `wikibase:label` service makes the full slice too heavy) and FR runs as one 500-id POST. Resumes from the last id via the `strsparqlcrawleritemswikidataid` server variable. |
| 110 | item fix INSTANCE_OF | `T_WC_WIKIDATA_ITEM_V1` (where `INSTANCE_OF IS NULL`) | Back-fills the `INSTANCE_OF` (P31) column for older items, in batches of 500. |
| 111 | cleaning | `T_WC_WIKIDATA_ITEM_PROPERTY` | De-duplicates `(ID_WIKIDATA, ID_PROPERTY, ID_ITEM)` triples by deleting redundant `ID_ROW`s. |
| 112 | move item to person | `T_WC_WIKIDATA_ITEM_V1` → `T_WC_WIKIDATA_PERSON_V1` | When an item's `INSTANCE_OF` matches the person whitelist (default `Q5`, configurable via the `strsparqlaltcrawlerpersoninstanceof` server variable) the row is moved into `_PERSON_V1` and removed from `_ITEM_V1`. Existing person rows are merged field-by-field (only NULL/empty fields are overwritten). SQL-only, no SPARQL requests. |
| 114 | serie properties | `T_WC_TMDB_SERIE` × `T_WC_IMDB_MOVIE_RATING_IMPORT` → `T_WC_WIKIDATA_ITEM_PROPERTY` | Same shape as 104 for series; POST batch size 50. Calls `tf.f_tmdbseriesetwikidatacompleted`. |
| 115 | person properties VIP | `T_WC_TMDB_PERSON` ⋈ `T_WC_TMDB_PERSON_SEARCH` → `T_WC_WIKIDATA_ITEM_PROPERTY` | Variant of 105 restricted to "VIP" persons (those present in `T_WC_TMDB_PERSON_SEARCH`) using a longer 100-day refresh window. POST batch size 25. |
| 116 | season properties | `T_WC_TMDB_SEASON` × `T_WC_IMDB_MOVIE_RATING_IMPORT` → `T_WC_WIKIDATA_ITEM_PROPERTY` | Same shape as 114 for TV seasons. Up to 1000 seasons per run (ranked by IMDb rating, refreshed > 30 days ago). POST batch size 50. Calls `tf.f_tmdbseasonsetwikidatacompleted`. Requires a `TIM_WIKIDATA_COMPLETED` column on `T_WC_TMDB_SEASON` (see [Required schema additions](#required-schema-additions)). |
| 117 | episode properties | `T_WC_TMDB_EPISODE` × `T_WC_IMDB_MOVIE_RATING_IMPORT` → `T_WC_WIKIDATA_ITEM_PROPERTY` | Same shape as 116 for TV episodes. Up to 2000 episodes per run (episodes are ~10× more numerous than seasons). POST batch size 50. Calls `tf.f_tmdbepisodesetwikidatacompleted`. Requires a `TIM_WIKIDATA_COMPLETED` column on `T_WC_TMDB_EPISODE` (see [Required schema additions](#required-schema-additions)). |
| 118–127 | T2S entity properties | `T_WC_T2S_<ENTITY>` → `T_WC_WIKIDATA_ITEM_PROPERTY` | Same shape as 116 but read from the Text2SQL read-model (`T_WC_T2S_*`) instead of the TMDb layer, because the data-prep pipeline populates `ID_WIKIDATA` reliably there (whereas the TMDb counterparts — e.g. `T_WC_TMDB_COLLECTION.ID_WIKIDATA` — are usually empty). All 10 scopes share one parameterized block keyed by `arrt2sscope` so the SPARQL pattern, batch size (50), 30-day refresh window, and `LIMIT 1000` stay in one place. The 10 entities and their helpers: **118 collection** (`f_t2scollectionsetwikidatacompleted`), **119 character** (`f_t2scharactersetwikidatacompleted`), **120 award** (`f_t2sawardsetwikidatacompleted`), **121 nomination** (`f_t2snominationsetwikidatacompleted`), **122 topic** (`f_t2stopicsetwikidatacompleted`), **123 technical** (`f_t2stechnicalsetwikidatacompleted`), **124 group** (`f_t2sgroupsetwikidatacompleted`), **125 movement** (`f_t2smovementsetwikidatacompleted`), **126 list** (`f_t2slistsetwikidatacompleted`), **127 death** (`f_t2sdeathsetwikidatacompleted`). Order is `IMDB_RATING_WEIGHTED DESC` for movie/serie-linked entities, `POPULARITY DESC` for the people-linked ones (group, death). Requires `TIM_WIKIDATA_COMPLETED` on each T2S table (see [Required schema additions](#required-schema-additions)). |

All property-fetch scopes (104 / 105 / 114 / 115 / 116 / 117 / 118–127) now POST a single SPARQL query per batch using a `VALUES ?item { … }` clause, rather than one request per id. Batch sizes are tuned to the per-item cost of the `?p ?statement . ?statement ?ps ?value` claim expansion and aim to stay under the WDQS 60-second timeout: 50 ids per POST for movies / series / seasons / episodes / T2S entities, 25 for persons (more claims per item), and the per-language scheme described above for item-add (109). The alias scopes (106, 107) and the item-fix scope (110) keep their existing batching. A `time.sleep(5)` sits between batches and a 60-second back-off retries on error.

### Configurable Wikidata "instance of" lists

Three Wikidata `P31` whitelists are persisted as server variables in the `T_WC_T2S_VARIABLE` table and lazily seeded with defaults on first run ([sparql-crawler.py:43-56](sparql-crawler.py#L43-L56)):

- `strsparqlaltcrawlerpersoninstanceof` — persons. Default: `Q5`.
- `strsparqlaltcrawlermovieinstanceof` — movies. Default: `Q11424 Q202866 Q226730 Q24862 Q20650540 Q506240 Q17517379`.
- `strsparqlaltcrawlerserieinstanceof` — series. Default: `Q5398426 Q1259759 Q117467246 Q63952888 Q15416`.

Edit these via the same DB layer if you want the person-move (scope 112) or other classification logic to accept additional Wikidata classes.

---

## Monitoring & runtime telemetry

The crawler reports progress by writing **server variables** through `cp.f_setservervariable` rather than logging to a file. Useful keys to dashboard against:

| Variable | Meaning |
|----------|---------|
| `strsparqlcrawlerstartdatetime` / `strsparqlcrawlerenddatetime` | Run boundaries (Europe/Paris). |
| `strsparqlcrawlertotalruntime` | Human-readable duration, or `RUNNING` while in-flight. Previous run is preserved in `strsparqlcrawlertotalruntimeprevious`. |
| `strsparqlcrawlerprocessesexecuted` | Comma-separated list of scope ids executed so far in this run. |
| `strsparqlcrawler{properties,movieproperties,serieproperties,seasonproperties,episodeproperties,personproperties,moviealiases,personaliases,items,itemfixinstanceof}currentprocess` | Human-readable label of the currently active scope. |
| `strsparqlcrawlert2s{collection,character,award,nomination,topic,technical,group,movement,list,death}propertiescurrentprocess` | Currently active T2S scope (118–127). Each scope also writes `*currentvalue` (the current batch label, e.g. `Q123..Q456 (50 ids)`) and `*wikidataid` (the last ID in the batch). |
| `strsparqlcrawler*wikidataid` / `strsparqlcrawler*currentvalue` | Latest Wikidata ID / ranking value being processed — these power external "current position" displays and let scope 109 resume from where it left off. |
| `strsparqlcrawler*processedcount` | Records picked up by the per-scope SELECT (`cursor.rowcount`), or for the SPARQL-only scope 100 the number of result rows returned by WDQS (`len(df)`). Compare against the per-scope LIMIT to see whether the cap was hit and how many `TIM_WIKIDATA_COMPLETED`-eligible rows were available. Written by every scope (100, 104, 105, 106, 107, 109, 110, 111, 112, 114, 115, 116, 117, 118–127); distinct counters for 105 / 115 and for 112 — see the prefix index below. |
| `strsparqlcrawler*processedseconds` | Wall-clock seconds spent in the scope's `if intindex == N:` block (from the start of the iteration through the end-of-iteration cleanup). Pair with `*processedcount` to compute records-per-second and size the per-scope LIMIT for the throughput you want. Written by every scope listed in `arrscopesvbasevar` — same prefix as `*processedcount`. |

`citizenphil.f_getservervariable` / `f_setservervariable` are the canonical accessors; the same variables are surfaced by the wider Citizenphil dashboards.

### Server-variable prefix index

Per-scope progress variables follow the pattern `<prefix>{currentprocess,currentvalue,wikidataid,processedcount,processedseconds}` (not every scope writes all five — the legacy series stub only writes `currentprocess`/`currentvalue`, and the item-fix scope only writes `currentvalue`/`wikidataid` for its progress trackers; scope 100 derives its `processedcount` from the SPARQL response since it has no SQL `SELECT`; `processedseconds` is written centrally via the `arrscopesvbasevar` mapping at the end of every iteration):

| Scope | Prefix |
|------:|--------|
| 100 | `strsparqlcrawlerproperties` |
| 103 (legacy) | `strsparqlcrawlerseries` |
| 104 | `strsparqlcrawlermovieproperties` |
| 105 | `strsparqlcrawlerpersonproperties` (note: a few sites write `strsparqlcrawlerpersonsproperties` with an extra `s` — both forms are in the wild) |
| 115 | `strsparqlcrawlerpersonproperties` for current* / wikidataid, but `strsparqlcrawlerpersonpropertiesvip` for `processedcount` so the VIP run is countable on its own |
| 106 | `strsparqlcrawlermoviealiases` |
| 107 | `strsparqlcrawlerpersonaliases` |
| 109 | `strsparqlcrawleritems` |
| 110 | `strsparqlcrawleritems` for `currentprocess`, `strsparqlcrawleritemfixinstanceof` for `currentvalue` / `wikidataid` / `processedcount` |
| 111 | `strsparqlcrawleritemsdedup` |
| 112 | `strsparqlcrawleritems` for `currentprocess`, `strsparqlcrawleritemfixinstanceof` for `currentvalue` / `wikidataid`, `strsparqlcrawlermoveitemtoperson` for `processedcount` |
| 114 | `strsparqlcrawlerserieproperties` |
| 116 | `strsparqlcrawlerseasonproperties` |
| 117 | `strsparqlcrawlerepisodeproperties` |
| 118 | `strsparqlcrawlert2scollectionproperties` |
| 119 | `strsparqlcrawlert2scharacterproperties` |
| 120 | `strsparqlcrawlert2sawardproperties` |
| 121 | `strsparqlcrawlert2snominationproperties` |
| 122 | `strsparqlcrawlert2stopicproperties` |
| 123 | `strsparqlcrawlert2stechnicalproperties` |
| 124 | `strsparqlcrawlert2sgroupproperties` |
| 125 | `strsparqlcrawlert2smovementproperties` |
| 126 | `strsparqlcrawlert2slistproperties` |
| 127 | `strsparqlcrawlert2sdeathproperties` |

Run-level variables (set once per run, no per-scope suffix):

| Variable | Meaning |
|----------|---------|
| `strsparqlcrawlerstartdatetime` / `strsparqlcrawlerenddatetime` | Run boundaries (Europe/Paris). |
| `strsparqlcrawlertotalruntime` / `strsparqlcrawlertotalruntimesecond` | Human-readable / seconds duration. `RUNNING` while in-flight. |
| `strsparqlcrawlertotalruntimeprevious` | Previous run's total duration, preserved before the new run overwrites the current value. |
| `strsparqlcrawlerprocessesexecuted` | Comma-separated list of scope ids executed so far in this run. |
| `strsparqlcrawlerprocessesexecutedprevious` | Same list from the previous run, preserved at startup. |
| `strsparqlcrawlercurrentprocess` / `strsparqlcrawlercurrentvalue` | Cleared between scopes; final state at end of run is empty. |
| `strsparqlcrawlercurrentsql` | Currently commented out; reserved for future per-scope SQL-trace surfacing. |

---

## Configuration

Runtime configuration is read from environment variables. Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

Required keys (see [.env.example](.env.example)):

- `WIKIMEDIA_USER_AGENT` — sent as the `User-Agent` on every SPARQL request; **must** identify you per the [Wikimedia UA policy](https://meta.wikimedia.org/wiki/User-Agent_policy), otherwise WDQS will return 429 or block you outright.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — MySQL connection used by `citizenphil`.
- `DB_NAMESPACE` — table prefix (the schema in this repo uses `T_WC_`).
- `USER_TIMEZONE` — IANA zone (default `Europe/Paris`); drives `cp.paris_tz` and all timestamp formatting.

`.env` is git-ignored and `.dockerignore`-ignored, so it is never committed and never baked into a Docker image.

### Python dependencies

Pinned in [requirements.txt](requirements.txt): `SPARQLWrapper`, `pandas`, `pymysql`, `requests`, `python-dotenv`, `pytz`, `thefuzz`, `beautifulsoup4`, `lxml`, `html5lib`, `schedule`, `numpy`.

The crawler also imports two local modules that are not on PyPI:

- [citizenphil.py](citizenphil.py) — DB connection (`f_getconnection`), `f_sqlupdatearray` upsert helper, server-variable get/set, timezone, duration formatting.
- [tmdb_functions.py](tmdb_functions.py) — TMDb-side update helpers (`f_tmdbmoviesetwikidatacompleted`, `f_tmdbpersonsetwikidatacompleted`, `f_tmdbseriesetwikidatacompleted`, `f_tmdbseasonsetwikidatacompleted`, `f_tmdbepisodesetwikidatacompleted`) and T2S-side helpers for scopes 118–127 (`f_t2scollectionsetwikidatacompleted`, `f_t2scharactersetwikidatacompleted`, `f_t2sawardsetwikidatacompleted`, `f_t2snominationsetwikidatacompleted`, `f_t2stopicsetwikidatacompleted`, `f_t2stechnicalsetwikidatacompleted`, `f_t2sgroupsetwikidatacompleted`, `f_t2smovementsetwikidatacompleted`, `f_t2slistsetwikidatacompleted`, `f_t2sdeathsetwikidatacompleted`), all built on the shared `_f_t2ssetwikidatacompleted(strtablename, strpkcolumn, lngid)` internal helper.

---

## Running locally

```bash
pip install -r requirements.txt
python ./sparql-crawler.py
```

The script is **single-shot**: it walks `arrwikidatascope` once, prints `Process completed`, and exits. Scheduling (cron, systemd timer, Docker restart loop) lives outside the script.

---

## Running with Docker

### Build

```bash
docker build -t sparql-crawler-python-app .
```

### Run

Secrets are **not** baked into the image. They are passed at runtime from a host-managed env file using Docker's `--env-file` option. The env file is expected to live outside the application source tree, for example at `/home/debian/docker/sparql-crawler/.env`:

```bash
docker run -d --rm \
    --network="host" \
    --env-file /home/debian/docker/sparql-crawler/.env \
    --name sparql-crawler \
    sparql-crawler-python-app
```

The shipped [sparql-crawler.sh](sparql-crawler.sh) launcher already uses this pattern.

### Why `--env-file` instead of `COPY .env`?

- The `.env` file is excluded from the build context by [.dockerignore](.dockerignore), so it cannot end up in image layers, build cache, or registries.
- The Dockerfile does not `COPY` `.env` and does not declare secrets in `ENV` lines — only non-sensitive defaults belong in the image.
- Secrets are supplied at `docker run` time only, and live on the host filesystem under operator control.

If you change the host path of the env file, update the `--env-file` argument in [sparql-crawler.sh](sparql-crawler.sh) accordingly.

---

## Customising the run

To enable / disable specific work, edit `arrwikidatascope` at [sparql-crawler.py:59](sparql-crawler.py#L59). Several alternate dictionaries are kept as commented-out presets — uncomment one (or build your own) and the next run will execute only those scopes, in the order they appear.

Each scope's SQL `LIMIT` is read from a per-process server variable (lazily seeded with the default on first run, then editable in `T_WC_T2S_VARIABLE` without touching the code). SPARQL `lngbatchsize` and the refresh window remain hard-coded inside each `if intindex == N:` block (or, for 118–127, inside the shared `arrt2sscope` block). Current defaults:

- `LIMIT` (rows pulled from MySQL per run, one server variable per scope — change the value in `T_WC_T2S_VARIABLE` to override):

  | Scope | Server variable | Default |
  | --- | --- | --- |
  | 104 (movie properties) | `strsparqlaltcrawlermoviepropertieslimit` | 10000 |
  | 105 (person properties, non-VIP) | `strsparqlaltcrawlerpersonpropertieslimit` | 20000 |
  | 106 (movie aliases) | `strsparqlaltcrawlermoviealiaseslimit` | 500 |
  | 107 (person aliases) | `strsparqlaltcrawlerpersonaliaseslimit` | 10000 |
  | 109 (item add — also drives end-of-cycle reset) | `strsparqlaltcrawleritemslimit` | 5000 |
  | 114 (serie properties) | `strsparqlaltcrawlerseriepropertieslimit` | 10000 |
  | 115 (person properties, VIP) | _no LIMIT — walks every eligible person_ | — |
  | 116 (season properties) | `strsparqlaltcrawlerseasonpropertieslimit` | 10000 |
  | 117 (episode properties) | `strsparqlaltcrawlerepisodepropertieslimit` | 20000 |
  | 118 (T2S collection) | `strsparqlaltcrawlert2scollectionpropertieslimit` | 10000 |
  | 119 (T2S character) | `strsparqlaltcrawlert2scharacterpropertieslimit` | 10000 |
  | 120 (T2S award) | `strsparqlaltcrawlert2sawardpropertieslimit` | 10000 |
  | 121 (T2S nomination) | `strsparqlaltcrawlert2snominationpropertieslimit` | 10000 |
  | 122 (T2S topic) | `strsparqlaltcrawlert2stopicpropertieslimit` | 10000 |
  | 123 (T2S technical) | `strsparqlaltcrawlert2stechnicalpropertieslimit` | 10000 |
  | 124 (T2S group) | `strsparqlaltcrawlert2sgrouppropertieslimit` | 10000 |
  | 125 (T2S movement) | `strsparqlaltcrawlert2smovementpropertieslimit` | 10000 |
  | 126 (T2S list) | `strsparqlaltcrawlert2slistpropertieslimit` | 10000 |
  | 127 (T2S death) | `strsparqlaltcrawlert2sdeathpropertieslimit` | 10000 |

- `lngbatchsize` (ids per SPARQL POST): 50 for movies / series / seasons / episodes / T2S entities (118–127), 25 for persons. Item-add (109) keeps the outer 500-id slice and sub-batches per language via `arrlangbatchsize = {1: 200, 2: 500}`.
- Refresh window: `strdatjminus30` (30 days, the common cutoff, also used by 118–127) and `strdatjminus100` (100 days, used by 115 / VIP persons).
- ORDER BY (T2S scopes 118–127): `IMDB_RATING_WEIGHTED DESC` for movie/serie-linked entities (collection, character, award, nomination, topic, technical, movement, list), `POPULARITY DESC` for people-linked entities (group, death).

Tune the LIMIT server variables when you need to widen / narrow a per-run pull without redeploying. Tune the hard-coded `lngbatchsize` in-place when you need to throttle WDQS load — smaller values lower the chance of hitting the WDQS 60-second timeout on heavy property expansions but multiply the number of HTTP round-trips.

---

## Required schema additions

Every property-fetch scope filters by `TIM_WIKIDATA_COMPLETED` and bumps it via a `f_*setwikidatacompleted` helper, so each source table must carry that column. `T_WC_TMDB_MOVIE`, `T_WC_TMDB_SERIE`, and `T_WC_TMDB_PERSON` already carry it.

The season (116) and episode (117) processes need it on `T_WC_TMDB_SEASON` / `T_WC_TMDB_EPISODE`:

```sql
ALTER TABLE T_WC_TMDB_SEASON
  ADD COLUMN TIM_WIKIDATA_COMPLETED datetime DEFAULT NULL,
  ADD KEY TIM_WIKIDATA_COMPLETED (TIM_WIKIDATA_COMPLETED);

ALTER TABLE T_WC_TMDB_EPISODE
  ADD COLUMN TIM_WIKIDATA_COMPLETED datetime DEFAULT NULL,
  ADD KEY TIM_WIKIDATA_COMPLETED (TIM_WIKIDATA_COMPLETED);
```

The T2S scopes (118–127) need it on each Text2SQL read-model table they crawl:

```sql
ALTER TABLE `T_WC_T2S_COLLECTION` ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_CHARACTER`  ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_AWARD`      ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_NOMINATION` ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_TOPIC`      ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_TECHNICAL`  ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_GROUP`      ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_MOVEMENT`   ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_LIST`       ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
ALTER TABLE `T_WC_T2S_DEATH`      ADD COLUMN `TIM_WIKIDATA_COMPLETED` datetime DEFAULT NULL, ADD KEY `TIM_WIKIDATA_COMPLETED` (`TIM_WIKIDATA_COMPLETED`);
```

`T_WC_T2S_GROUP` is backticked because `GROUP` is a MySQL reserved word; the SELECTs in the crawler use the same convention.
