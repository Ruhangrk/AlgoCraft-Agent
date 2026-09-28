# Routers (overview)

Full per-router docs: **`docs/cpp/routing/INDEX.md`**.

Registered names:
- `default_router` — 14 sessions, all PnL>0 winners
- `top15_week_router` — 5 sessions, top 15 by PnL
- `live_run_testing_router` — 1 session, top 3, `live_run_testing` only

Agent v1 generates **strategies** only; pick an existing router for `runs/start`. Prefer past `anchor_date` for hist.
