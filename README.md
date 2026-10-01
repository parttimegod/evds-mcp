# evds-mcp

[![test](https://github.com/parttimegod/evds-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/parttimegod/evds-mcp/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

MCP server for the Central Bank of Türkiye's statistical database (EVDS).
Lets Claude and other MCP clients search, fetch and analyse Turkish
macroeconomic time series, with stationarity testing built into the
relationship analysis.

## Features

- Concept-based series search in Turkish and English
- Single or multi-series data retrieval
- ADF checks at level, log difference and successive differences
- Relationship analysis with automatic transformation, lag scanning and
  Engle-Granger cointegration testing
- Turkish text normalisation for search

## Installation

No install needed. Point your MCP client at it:

```json
{
  "mcpServers": {
    "evds": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/parttimegod/evds-mcp", "evds-mcp"],
      "env": { "EVDS_API_KEY": "your-api-key" }
    }
  }
}
```

Claude Desktop uses `claude_desktop_config.json`; Claude Code uses
`~/.claude.json`. No clone, no path, no virtualenv — `uvx` fetches and
runs it.

Get a free API key at [evds3.tcmb.gov.tr](https://evds3.tcmb.gov.tr):
register, then "Copy API Key" at the bottom of your profile page.

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

<details>
<summary>Working on the code instead?</summary>

```bash
git clone https://github.com/parttimegod/evds-mcp
cd evds-mcp
uv sync
uv run pytest
```

Then point the config at your checkout:

```json
"args": ["--directory", "/path/to/evds-mcp", "run", "evds-mcp"]
```

</details>

## Usage

Once configured, ask in plain language:

```
Get CPI and the policy rate since 2020
How far back does the house price index go?
Is there a relationship between the dollar rate and inflation?
```

Relationship analysis returns the transformation, ADF p-values,
correlation and any requested lag profile. It also returns the level
correlation with an interpretation note. Tool output messages are in Turkish.

## Tools

### `search_series(query, limit=10)`

Finds series codes from a concept. Series codes such as `TP.FG.J0` are
not memorable, so every session starts here. Queries work in Turkish and
English.

Returns code, name, English name, data group, frequency, source and
coverage dates for each match.

### `summarize_series(code, start, end, frequency="monthly")`

Summarises a series without returning raw observations: count, missing
values, first and last value, min, max, mean, total change.

### `get_series(codes, start, end, frequency="monthly", full=False)`

Fetches series data. Accepts multiple codes and returns them aligned on
the same date grid.

By default it returns a summary plus the last 24 observations. A monthly
series starting in 2003 has around 280 observations, and requesting a few
of them at once fills the context window. Pass `full=True` for everything.

### `test_stationarity(code, start, end, frequency="monthly")`

Runs ADF at level, on the log difference and on successive differences.
Returns an I(d) classification and a transformation based on that test
rule. This classification depends on the sample and test settings.

### `analyze_relationship(codes, start, end, frequency="monthly", transform=None, max_lag=0)`

Analyses the relationship between two series. Both are tested for
stationarity first, the required transformation is applied, and the
output states which transformation was used. If both series are classified as I(1), it
also runs an Engle-Granger cointegration test.

- `transform` — set the transformation manually: `logd1`, `d1`, `d2`,
  `level`
- `max_lag` — scan lagged relationships and report the strongest lag

Frequency values accept both English and Turkish: `daily`, `business`,
`weekly`, `semimonthly`, `monthly`, `quarterly`, `semiannual`, `annual`.

## Interpreting relationship output

The server exposes relationship analysis with ADF checks rather than a
standalone correlation command. A high level correlation between trending
series is easy to overinterpret; the tests and transformation therefore
travel with the number.

ADF uses a constant term, AIC lag selection and a 5% threshold.
Failure to reject a unit root is not proof that a series is non-stationary.
The returned integration degree is a working classification under those
settings, not a property established for every period.

Automatic selection applies the higher suggested difference order to both
series. That can over-difference the other series. Use `transform` to
compare a chosen specification; the output warns when its available ADF
result does not reject a unit root.

Lag scanning selects the largest absolute correlation in the same sample.
It does not correct for multiple comparisons or validate the selected lag
on new data. Neither that peak nor a cointegration result establishes
causality.

The MCP analysis drops missing values, and relationship analysis keeps
only complete date pairs. Its differences and lags count those remaining
observations, so a lag can span a gap. The PostgreSQL calendar-lag method
below is separate from this analysis path.

[ASAMA2.md](ASAMA2.md) records the earlier USD/TRY–CPI comparison, the
current calculation settings and a command for repeating it.

## Optional PostgreSQL storage

`evds_mcp.depo` is an optional storage layer for series metadata and
observations. It exists for three reasons: to avoid re-fetching a series
that is already stored, to query history with SQL (which the EVDS client
itself does not offer — it only returns one request's response), and to
keep provenance: which fetch wrote which value, and when.

It is not installed by default. Install the extra:

```bash
uv sync --extra depo
```

`import evds_mcp` works with no database and no `psycopg` installed;
`depo.py` only imports `psycopg` when a `Depo` method actually runs, and
raises a clear error naming the extra if it is missing.

```python
from datetime import date
from evds_mcp.depo import Depo

depo = Depo("host=127.0.0.1 port=5432 dbname=evds user=postgres")
depo.kur()  # applies the schema, safe to call again later

depo.seri_yaz(kunye)                              # upsert one series' metadata
depo.gozlem_yaz(kod, date(2020, 1, 1), date(2020, 12, 31), gozlemler)
                                                   # bulk upsert observations,
                                                   # records a cekim audit row
depo.son_gozlemler(kod, 12)                       # last 12 observations, newest first
depo.cekimler_oku(kod)                            # fetch history for this series
depo.gecikmeli_oku(kod, 1)                        # row-wise lag (fast, gap-blind)
depo.takvim_gecikmeli_oku(kod, 1)                 # calendar-aware lag (correct on gaps)
depo.salt_okunur_sorgu("SELECT ...")              # guarded read-only SQL, see below
```

### Storage schema

| Table | Key | Stores |
|---|---|---|
| `seri` | `kod` | Series metadata and frequency |
| `cekim` | Generated ID | Requested range, fetch time and observation/NULL counts |
| `gozlem` | `(kod, tarih)` | Latest value, original period label and fetch reference |

The DDL is in [sema.sql](src/evds_mcp/sema.sql). A fetch record and its
observation upserts are committed together. If one observation fails,
both roll back. Re-fetching updates existing values rather than adding
duplicates. The fetch records remain, but previous versions of an
observation value are not retained.

A missing value is stored as `NULL`, not zero. `ham_donem` keeps the
original period label alongside its parsed date. Values use `NUMERIC`
for decimal arithmetic in PostgreSQL. The current EVDS client parses
numbers as Python floats before storage, so this does not preserve every
digit of the original API string. Direct `Decimal` inputs avoid that
conversion.

The `(kod, tarih)` primary-key index can scan backwards for
`WHERE kod = ... ORDER BY tarih DESC LIMIT ...`. The
[240,000-row plan example](examples/sql/indeks_plani.sql) runs in CI and
shows this without a separate sort. New installations no longer create
the duplicate DESC index; existing installations may still have it.

### Row lag and calendar lag

`gecikmeli_oku(kod, n)` uses `LAG` over stored rows. That is suitable
when all periods are present. If January and March exist but February
has no row, March's `LAG(1)` returns January, which is two months earlier.

`takvim_gecikmeli_oku` builds a calendar with `generate_series`, joins
observations onto it and then applies `LAG`. February becomes an explicit
NULL row, so March's one-month lag is NULL. The calendar covers the
locally stored minimum and maximum dates.

Calendar lag supports daily, monthly, quarterly, semiannual and annual
series. Business-day calendars need holidays, weekly dates may move on
holidays, and the semimonthly anchors have not been verified. Those three
frequencies therefore use the row-lag method.

The [SQL quality example](examples/sql/veri_kalitesi.sql) shows the same
gap case and guards percentage changes against division by zero.
[Comparing two series](examples/sql/iki_seri_karsilastirma.sql) keeps only
dates where both have values.

### Read-only SQL

`salt_okunur_sorgu(sql, limit=200, zaman_asimi_ms=5000)` runs one
`SELECT`, `WITH`, `SHOW`, or `EXPLAIN` statement and returns rows as
dicts. It rejects semicolon-separated statements, runs under
`transaction_read_only`, applies a statement timeout, and uses prepared
execution — which, combined with the single-statement check, blocks a
`COMMIT`/`SET`-style escape chain. This is read-only execution, not a
security sandbox: only pass it SQL you trust.

## Python API

The library can be used directly. Note that internal method names are in
Turkish; the MCP tool names are English.

```python
from datetime import date
from evds_mcp.client import EVDS
from evds_mcp.catalog import Katalog

with EVDS() as evds:
    k = Katalog(evds)

    k.grup_ara("inflation")                # bie_tukfiy2025
    k.seri_ara("genel", "bie_tukfiy2025")  # TP.TUKFIY2025.GENEL

    series = evds.veri(
        ["TP.TUKFIY2025.GENEL"],
        date(2025, 1, 1),
        date(2025, 5, 1),
    )
```

## Notes on the EVDS API

The service endpoint is:

```
https://evds3.tcmb.gov.tr/igmevdsms-dis/
```

Most examples online still point at `evds2.tcmb.gov.tr/service/evds/`,
which now redirects to the web interface and returns HTML.

| Topic | Behaviour |
|---|---|
| Authentication | HTTP header (`key`). It was a URL parameter before 2024 |
| Parameter format | Appended to the path: `.../igmevdsms-dis/series=TP.FG.J0&startDate=...` |
| Using `params=` | Adds a leading `?`, which the service rejects |
| Date format | `DD-MM-YYYY`. A wrong format returns a different range instead of an error |
| Bulk series endpoint | None. Series are fetched per data group |
| Column names | Request `TP.FG.J0`, response contains `TP_FG_J0` |
| International groups | Sorted alphabetically; Türkiye can be at position 470 |

In Python, `"I".lower()` returns `"i"` rather than `"ı"`, which silently
breaks search on Turkish text. Normalisation lives in `text.py`.

Responses are UTF-8. If Turkish characters look broken, the terminal
code page is the cause.

## Tests

```bash
uv run pytest          # offline, against recorded fixtures
uv run pytest -m live  # hits the real API, needs EVDS_API_KEY
uv run --extra depo pytest -m depo  # hits a real PostgreSQL
```

GitHub Actions runs the offline tests and the PostgreSQL tests in separate
jobs. The latter starts a disposable PostgreSQL service and uses only test
data. Fixtures under `tests/fixtures/` are real EVDS responses.

## License

MIT
