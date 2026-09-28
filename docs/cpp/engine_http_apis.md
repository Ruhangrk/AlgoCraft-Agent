# Engine HTTP tools (Phase A)

JWT required after login. Prefer past `anchor_date` for hist runs (not live).

## Auth / discovery
| Method | Path | Notes |
|--------|------|--------|
| POST | `/auth/login` | returns JWT |
| GET | `/strategies` | registered strategy names |
| GET | `/routing-algos` | router names |
| GET | `/instruments?q=&limit=` | ticker search |
| POST | `/market-data/ensure` | ensure bars for tickers/range (UI body) |

## Workbooks
| Method | Path | Body / notes |
|--------|------|----------------|
| POST | `/workbooks` | `{name, capital_paise}` → `{id}` |
| GET | `/workbooks/{wid}` | workbook row |

## Backtest (sync)
`POST /workbooks/{wid}/backtests/start`

Required: `ticker`, `strategy`, `from_ns`, `to_ns`, `capital_paise`.  
Optional: `order_qty`, ema knobs, etc.  
Response `201` includes `id`, `fills`, `pnl_paise`, …

`GET .../backtests/{id}` and `.../events` for detail.

## Hist / live run
`POST /workbooks/{wid}/runs/start`

Body essentials: `router`, `capital_paise`, `anchor_date` (`YYYY-MM-DD`).  
Agent should prefer a **closed past session** for hist replay.

Also: `POST .../runs/stop`, `GET .../runs/{rid}`, `GET .../runs/{rid}/events?include=routing,fill`.

## Time helpers (Python)
Use `zoneinfo.ZoneInfo("Asia/Kolkata")` to build `from_ns` / `to_ns` as UTC epoch nanos matching AlgoCraft session calendar.  
“Last week” → last ~5 NSE session days ending at last **closed** session.

## Soft eval (agent policy)
After a run/backtest: check fills in a band (e.g. 2–5000) and soft min PnL; iterate research/propose rather than claiming success on empty books.
