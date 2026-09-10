# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
