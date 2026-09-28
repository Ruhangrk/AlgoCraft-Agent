# Indicators (overview)

Full per-indicator docs: **`docs/cpp/indicators/INDEX.md`**.

Quick rules:
- Container updates indicators before `on_bar`
- Bind with `lib.get<T>(symbol, resolution, args...)` in `configure`
- Always check `ready()` before `value()`
- Built-ins: Ema, Sma (daily), LaggedSma, Vwap, Rsi + daily SMA warmup helpers

Fetch `indicators/library.md` plus the specific indicator file when coding.
