# Prosperity Scope

Trading analytics dashboard for [IMC Prosperity 4](https://prosperity.imc.com/) — a global algorithmic trading competition with 22,000+ participants.

**Live:** [prosperity-scope.vercel.app](https://prosperity-scope.vercel.app)

Drop a backtest log onto the page to get instant market microstructure analysis — Hurst exponent, order book imbalance, fill quality, P&L attribution, all computed in-browser.

---

## Try It

1. Go to [prosperity-scope.vercel.app](https://prosperity-scope.vercel.app)
2. Download [`sample/demo_run.log`](sample/demo_run.log) from this repo
3. Drag it onto the page

Or run the included demo trader yourself:

```bash
pip install -e backtester/
python -m prosperity4bt demo/trader_v1.py 0--1 0--2 --merge-pnl --out my_run.log
```

Then drag `my_run.log` onto the dashboard.

---

## What It Shows

| Tab | Description |
|-----|-------------|
| **Price & Trades** | Mid price with bid/ask, fair value, EMA, Bollinger Bands. Buy/sell fills plotted as markers. |
| **P&L Curve** | Cumulative profit with drawdown visibility. |
| **Microstructure** | Bid-ask spread over time + Order Book Imbalance (OBI). |
| **Volume Profile** | Fill distribution by price level. |
| **Trade Log** | Every executed trade in a sortable table. |

**Metrics bar:** Final P&L, max drawdown, Hurst exponent (regime classification), volatility, autocorrelation, average spread, fill counts.

Supports backtester `.log` files, Prosperity submission `.json` files, and lambda log arrays.

---

## Architecture

```
index.html              Single-file dashboard — no build, no framework
demo/
  trader_v1.py           Demo trading algorithm (market-making + mean reversion)
  datamodel.py           Prosperity 4 type definitions
sample/
  demo_run.log           Pre-generated backtest output
```

The entire dashboard is one HTML file. Plotly.js from CDN, vanilla JS, zero dependencies. Parsing, Hurst computation, FFT, and OBI correlation all run client-side.

---

## The Demo Trader

`demo/trader_v1.py` is a market-making algorithm for the tutorial round products:

- **EMERALDS** (stable asset) — wall-mid fair value, overbid/undercut quoting, aggressive taking of mispriced levels
- **TOMATOES** (mean-reverting) — VWAP fair value, inventory-aware position management, soft limits with skew

It logs `SIG|` signal lines that the dashboard reads to render fair value overlays, Bollinger Bands, and OBI charts.

---

## Deploy Your Own

```bash
git clone https://github.com/nikhilboya/prosperity-scope.git
vercel deploy --prod
```

Or just open `index.html` locally — it works offline.
