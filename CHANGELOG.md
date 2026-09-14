# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-09-14

### Fixed

- Calendar-aware lag (`Depo.takvim_gecikmeli_oku`). The original lag
  implementation, `LAG(deger, n) OVER (ORDER BY tarih)`, returns the
  previous *stored row*, not the previous *calendar period*. When a
  period is absent from the table entirely — no row at all, as opposed
  to a row with a NULL value — LAG silently skips it, and a two-period
  gap gets reported as a one-period lag. Measured, on a monthly series
  with 2020-03 absent, `gecikme=1`:

  ```
  row-wise                          calendar-aware
  2020-02-01  2  <- 1               2020-02-01  2  <- 1
  2020-04-01  4  <- 2   WRONG       2020-03-01  ·  <- 2   (absent, explicit NULL)
                                    2020-04-01  4  <- ·   CORRECT
  ```

  On a macro series with gaps — a period not yet published, a partial
  re-fetch, a range never pulled — this produces a wrong lag
  correlation, silently, which is the exact class of error this project
  exists to prevent. The fix builds the expected calendar grid with
  `generate_series` at the interval implied by the series' frequency,
  left-joins observations onto it, then applies LAG over that grid, so
  absent periods become explicit NULL rows and the lag is
  calendar-correct by construction. Both methods remain available
  (`gecikmeli_oku` stays the fast, gap-blind row-wise version); the bug
  was having only the row-wise one and not documenting which behavior
  it had.

### Added

- Optional PostgreSQL storage layer (`evds_mcp.depo`), behind a `depo`
  extra (`psycopg[binary]`). `import evds_mcp` still works with no
  database and no `psycopg` installed; `psycopg` is only imported on
  first actual use of a `Depo` method.
- Three tables: `seri` (series metadata), `gozlem` (observations), and
  `cekim`, a fetch-audit table recording the requested range, fetch
  time, observation count, and null count for every write — so a
  stored number's provenance is answerable. Macro data gets revised;
  "where did this come from and when" is not a luxury.
- `Depo.salt_okunur_sorgu()`, a read-only SQL escape hatch: single
  statement, `SELECT`/`WITH`/`SHOW`/`EXPLAIN` only, run in a read-only
  transaction with a statement timeout.
- `examples/sql/`: two runnable, commented queries
  (`veri_kalitesi.sql`, `iki_seri_karsilastirma.sql`).

### Changed

- `gozlem.deger` is `NUMERIC`, not `DOUBLE PRECISION` — these are price
  indices and exchange rates, and binary floating point makes exact
  comparison and summation lossy.
- `gozlem.ham_donem` keeps the original EVDS period label, because
  EVDS's period strings differ across frequencies (`"2020-3"`,
  `"01-01-2020"`) and a parsing bug is then debuggable rather than
  invisible.
- `gozlem.deger` is nullable: a missing observation is not zero.
  Storing zero would corrupt every mean and every difference.
- Primary key `(kod, tarih)` makes re-fetching idempotent; index
  `(kod, tarih DESC)` serves the dominant "last N observations" query
  without a sort.
- `takvim_gecikmeli_oku` raises `DepoHatasi` rather than guessing a
  calendar grid for business-day, weekly, and semimonthly frequencies:
  public holidays shift those, so no fixed step reliably exists.

## [0.1.0] - 2026-09-07

### Added

- Concept-based series search across TCMB's data groups, in Turkish and
  English (`search_series`)
- Single or multi-series data retrieval aligned on a common date grid
  (`get_series`), plus a summary-only variant (`summarize_series`)
- ADF stationarity testing and order-of-integration detection
  (`test_stationarity`)
- Relationship analysis with automatic transformation selection, lag
  scanning, and Engle-Granger cointegration testing for I(1) pairs
  (`analyze_relationship`)
- Turkish text normalisation for search, working around Python's
  `str.lower()` mishandling Turkish characters (`İ`/`I`)
- Packaging for `uvx` — no clone, virtualenv or local path needed to run
  the server
- MIT license and CI (ruff and pytest on push/PR)

### Notes

- No tool computes a raw level correlation. Macroeconomic series are
  usually non-stationary, so a level correlation is spurious.
  `analyze_relationship` still reports the level correlation, labelled
  as not to be used.
