# evds-mcp

[![test](https://github.com/parttimegod/evds-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/parttimegod/evds-mcp/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

MCP server for the Central Bank of Türkiye's statistical database (EVDS).
Lets Claude and other MCP clients search, fetch and analyse Turkish
macroeconomic time series, with stationarity testing built into the
relationship analysis.

## Features

- Concept-based series search across 676 data groups (Turkish and English)
- Single or multi-series data retrieval
- ADF stationarity testing and order-of-integration detection
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

The last question produces the following. First the model looks up codes:

```jsonc
// search_series("dollar exchange rate")
{
  "seriler": [
    {
      "kod": "TP.DK.USD.A.YTL",
      "ad_eng": "(USD) US Dollar (Buying)",
      "grup": "bie_dkdovytl",
      "frekans": "GÜNLÜK",
      "kapsam": "02-01-1950 - 27-08-2026"
    }
  ]
}
```

Then analyses the relationship. Note that the level correlation is
returned but flagged, and the strongest relationship is not
contemporaneous:

```jsonc
// analyze_relationship(["TP.DK.USD.A.YTL", "TP.TUKFIY2025.GENEL"],
//                      "2010-01-01", "2026-06-01",
//                      transform="logd1", max_lag=6)
{
  "donusum": "logd1",
  "korelasyon": 0.421,
  "gozlem": 197,
  "gecikme": {
    "profil": { "0": 0.421, "1": 0.5685, "2": 0.3359, "3": 0.2079 },
    "tepe_gecikme": 1,
    "tepe_korelasyon": 0.5685
  },
  "ham_seviye_korelasyonu": {
    "deger": 0.9856,
    "uyari": "Bu rakamı kullanma. Seriler durağan olmadığı için sahte
              regresyon; ortak trend yüzünden şişkin çıkıyor."
  },
  "uyarilar": [
    "Bütünleşme dereceleri farklı: TP.DK.USD.A.YTL I(1),
     TP.TUKFIY2025.GENEL I(2).",
    "TP.TUKFIY2025.GENEL: istenen dönüşüm (logd1) bu seriyi
     durağanlaştırmıyor (ADF p=0.3512). Sonuç şişkin olabilir.",
    "En güçlü ilişki 1. gecikmede (0.5685), eşanlı değil (0.421)."
  ],
  "yorum": "Bu bir korelasyondur, nedensellik değildir."
}
```

Tool output messages are in Turkish.

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
Returns the order of integration I(d) and the recommended transformation.

### `analyze_relationship(codes, start, end, frequency="monthly", transform=None, max_lag=0)`

Analyses the relationship between two series. Both are tested for
stationarity first, the required transformation is applied, and the
output states which transformation was used. If both series are I(1) it
also runs an Engle-Granger cointegration test.

- `transform` — set the transformation manually: `logd1`, `d1`, `d2`,
  `level`
- `max_lag` — scan lagged relationships and report the strongest lag

Frequency values accept both English and Turkish: `daily`, `business`,
`weekly`, `semimonthly`, `monthly`, `quarterly`, `semiannual`, `annual`.

## Why there is no raw correlation tool

There is no tool that computes a level correlation. Macroeconomic series
are usually non-stationary, and correlating them at level produces
spurious results driven by a shared trend.

USD/TRY and CPI, monthly, 2010-01 to 2026-06:

| Method | Correlation | Note |
|---|---|---|
| Level | 0.99 | Spurious regression (ADF p = 1.00 and 0.99) |
| Automatic transform (d2) | 0.15 | Over-differenced: USD/TRY is I(1), CPI is I(2) |
| Log difference + 1 month lag | 0.57 | |

Lag profile:

```
0 months  +0.42
1 month   +0.57
2 months  +0.34
3 months  +0.21
```

`analyze_relationship` still returns the level correlation, labelled with
a warning.

Turkish CPI is I(2) over this period: neither first differencing nor log
differencing makes it stationary. Full ADF output is in
[ASAMA2.md](ASAMA2.md) (Turkish).

## Optional PostgreSQL storage

`evds_mcp.depo` is an optional storage layer for series metadata and
observations. It exists for two reasons: to avoid re-fetching a series
that is already stored, and to query history with SQL, which the EVDS
client itself does not offer (it only returns one request's response).

It is not installed by default. Install the extra:

```bash
uv sync --extra depo
```

`import evds_mcp` works with no database and no `psycopg` installed;
`depo.py` only imports `psycopg` when a `Depo` method actually runs, and
raises a clear error naming the extra if it is missing.

```python
from evds_mcp.depo import Depo

depo = Depo("host=127.0.0.1 port=5432 dbname=evds user=postgres")
depo.kur()  # applies the schema, safe to call again later

depo.seri_yaz(kunye)              # upsert one series' metadata
depo.gozlem_yaz(kod, gozlemler)   # bulk upsert observations
depo.son_gozlemler(kod, 12)       # last 12 observations, newest first
depo.gecikmeli_oku(kod, 1)        # each observation with the prior period's value
```

### Schema

```sql
CREATE TABLE seri (
    kod TEXT PRIMARY KEY, ad TEXT, ad_eng TEXT, grup TEXT,
    frekans SMALLINT, kaynak TEXT, baslangic DATE, bitis DATE,
    guncelleme TIMESTAMPTZ
);
CREATE TABLE gozlem (
    kod TEXT REFERENCES seri(kod) ON DELETE CASCADE,
    tarih DATE NOT NULL,
    deger DOUBLE PRECISION,
    cekilme TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (kod, tarih)
);
CREATE INDEX ON gozlem (kod, tarih DESC);
```

Four decisions in this schema are worth explaining, since they are not
obvious from the DDL alone:

- **`deger` is nullable.** A missing observation is not zero. EVDS
  returns null for a period a series was not published in yet. Storing
  0 would silently corrupt every mean and every difference computed
  over the series.
- **The primary key is `(kod, tarih)`**, the natural key of an
  observation. It makes re-fetching a series idempotent through
  `ON CONFLICT ... DO UPDATE`, and it makes a duplicate observation
  impossible rather than merely unlikely.
- **The index is `(kod, tarih DESC)`**, not `(kod, tarih)`. The
  dominant query is "the last N observations of this series"
  (`son_gozlemler`); descending order lets that be a plain index scan
  with no sort step.
- **All frequencies live in one table.** The date is the source of
  truth; frequency is a property of the series, not of the
  observation. A separate table per frequency would turn a query
  across series of different frequencies into a union.

### The lag query

`gecikmeli_oku(kod, gecikme)` is the point of this layer: it returns
each observation next to the value some number of periods earlier,
using a window function instead of a self-join.

```sql
SELECT tarih, deger,
       LAG(deger, %s) OVER (PARTITION BY kod ORDER BY tarih) AS onceki
FROM gozlem
WHERE kod = %s
ORDER BY tarih
```

The first `gecikme` rows of a series have no prior value; `LAG` returns
`NULL` for them rather than requiring special-case handling in Python.

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
uv run pytest -m depo  # hits a real PostgreSQL, needs the depo extra installed
```

Fixtures under `tests/fixtures/` are real EVDS responses.

## License

MIT
