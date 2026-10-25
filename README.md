# 📡 DOM Mutation Radar

An autonomous resilience infrastructure running entirely on GitHub Actions. It monitors interactive UI elements across web platforms, tests selector stability, and serves verified CSS/XPath mapping dictionaries to prevent browser-use agents from crashing during frontend deployments.

## Token & Tool-Call Reduction
- **Failure Prevention**: Eliminates repeated DOM inspection loops and broken-selector retries for browser-use agents.
- **Payload**: Compact JSON mapping of verified primary and fallback selectors.

## Machine Feeds
- [`v1/active-selectors.json`](public/v1/active-selectors.json) (Active selector map)
- [`v1/selector-mutations.json`](public/v1/selector-mutations.json) (Drift alerts)
- [`llms.txt`](public/llms.txt) (Token-efficient LLM digest)
- `selectors.parquet` (Columnar database snapshot)

## Architecture
- **Verification Engine**: BeautifulSoup4 DOM hierarchy crawler
- **Database**: DuckDB + Parquet
- **Ledger**: Append-only Git-committed JSONL in `/data/history`
- **Edge CDN**: GitHub Pages (Fastly CDN)
