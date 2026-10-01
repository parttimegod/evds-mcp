# Changelog

## Unreleased

- PostgreSQL CI checks batch rollback and runs the 240,000-row index-plan
  example. Fresh schemas rely on the primary-key index for latest-value
  queries; existing duplicate DESC indexes are left in place.
- Clarified that NUMERIC storage cannot recover API digits already
  converted to float by the client.
- Relationship output now distinguishes ADF rejection from proof of
  stationarity, integration degree or cointegration.
- Stationary pairs no longer receive the non-stationary level warning.
  Forced `level` and `seviye` transformations use the same ADF warning.
- Updated methodology notes to separate historical results from the
  current calculation rule and its limits.

## [0.2.0] - 2026-09-14

- Added optional PostgreSQL storage through the `depo` extra, with lazy
  psycopg imports.
- Added series metadata, latest observations and fetch records. A fetch
  record and its observation upserts share one transaction.
- Added calendar-aware lag using `generate_series`. Missing stored rows
  become explicit NULL periods rather than being skipped by row-wise LAG.
- Kept row-wise lag available for callers who need that behaviour.
  Business-day, weekly and semimonthly calendars remain unsupported by
  the calendar method.
- Used nullable NUMERIC values and retained original EVDS period labels.
  The client still parses API numbers as float.
- Used `(kod, tarih)` as the observation key for repeated fetches.
  The additional DESC index introduced here is no longer created in
  fresh schemas.
- Added guarded read-only SQL with a statement timeout and runnable
  quality/comparison queries.

## [0.1.0] - 2026-09-07

- Added series search in Turkish and English, data retrieval and summaries.
- Added ADF checks, transformation selection, lag scanning and
  Engle–Granger testing for pairs classified as I(1).
- Added Turkish text normalisation for catalogue search.
- Packaged the MCP server for `uvx`.
- Added MIT licensing and offline fixture tests in CI.

The relationship tool includes the level correlation with an interpretation
note. There is no separate raw-correlation MCP command.
