# Agent strategy HTTP APIs

Base: AlgoCraft engine (default `http://127.0.0.1:8080`). All routes need JWT (`Authorization: Bearer …`).

## GET /agent/strategies/catalog
Returns array of catalog rows: `id`, `kind`, `name`, `class_name`, `enabled`, `hpp_path`, `cpp_path`, `sandbox_path`, `provenance`, `compile_ok`, timestamps.

## POST /agent/strategies/compile
Body:
```json
{
  "name": "my_mean_revert",
  "class_name": "MyMeanRevert",
  "kind": "strategy",
  "hpp": "#pragma once\n...",
  "cpp": "#include \"algocraft/strategies/my_mean_revert.hpp\"\n..."
}
```

- Writes sandbox under `data/agent_sandbox/<name>/`.
- Runs `g++ -std=c++20 -fsyntax-only` against sandbox + project includes.
- `200` + `{ok:true, ...}` on success; `422` + `{ok:false, log}` on failure.
- Updates catalog `compile_ok` when a row exists; does **not** enable.

Use `log` text to repair code in the compile loop.

## POST /agent/strategies/promote
Body: `{ "name": "my_mean_revert" }`

- Requires successful sandbox artifacts.
- Copies to `include/algocraft/strategies/<name>.hpp` and `src/strategies/<name>.cpp`.
- Patches `CMakeLists.txt` + `strategy_registrations.cpp`.
- Upserts catalog with **`enabled=false`**.
- `201` response includes paths + note.

Never promote without human confirmation.

## POST /agent/strategies/activate
Body: `{ "name": "my_mean_revert", "enabled": true }`

- Flips catalog `enabled` (pass `false` / `0` to hide).
- Does **not** hot-load C++; note says rebuild engine and restart `serve`.
- `404` if name not promoted first.

## Tool timeouts (agent side)
Compile ~180s; light GETs ~120s; heavy run/backtest up to ~600s.
