# ngxlistedcompanies → PostgreSQL migration

Company issuer data previously stored in MongoDB (`ngxlistedcompanies.<symbol>`) now lives in Django Postgres as `portfolio_companyprofile` (OneToOne with `portfolio_stock`).

## Django

- **Model:** `portfolio.models.CompanyProfile`
- **Service:** `portfolio.company_profile` (`upsert_from_ngx_data`, `get_symbol_overview`, `get_shares_outstanding`)
- **Sync from NGX API:** `python manage.py company-details`
- **One-time Mongo import:** `python manage.py migrate_ngxlistedcompanies [--mongo-db ngxlistedcompanies] [--dry-run]`

## API for price pipelines

Replace Mongo `SharesOutstanding` lookups with:

| Endpoint | Response |
|----------|----------|
| `GET /portfolio/shares-outstanding/` | `{"ZENITHBANK": 15794462835.0, ...}` |
| `GET /portfolio/shares-outstanding/<symbol>/` | `{"symbol": "ZENITHBANK", "shares_outstanding": 15794462835.0}` |

Market cap: `shares_outstanding * current_price` (unchanged formula).

## Direct Postgres (market_data_system)

`market_data_system/common/db/postgres.py` exposes:

- `postgres_db.get_shares_outstanding(symbol)`
- `postgres_db.get_all_shares_outstanding()`

Set `POSTGRES_URL` in `market_data_system/config/.env` to the same database as Django.

## TradingView scripts

Update `get_symbol_cap()` / `get_all_symbol_caps()` in:

- `tradingView-API/unified_price_system3.py`
- `tradingView-API/docker/unified_price_system3.py`
- `tradingView-API/docker/unified_price_system4.py`
- `tradingView-API/close_price7.py`
- `tradingView-API/go_format/unified_price_system.go`

Options: HTTP call to `/portfolio/shares-outstanding/`, or `psycopg2`/`SQLAlchemy` query on `portfolio_companyprofile`.
