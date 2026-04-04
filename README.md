# Prosperity Scope

Trading analytics dashboard for [IMC Prosperity 4](https://prosperity.imc.com/).

Upload a backtest `.log` file and get instant analysis across five tabs: price charts with trade overlays, P&L curves, microstructure (spread + OBI), volume profile, and a full trade log.

**Live:** Open `index.html` in any browser — no install, no build step, no dependencies.

---

## Features

| Tab | What it shows |
|-----|---------------|
| **Price & Trades** | Mid price with best bid/ask, fair value, EMA, and Bollinger Band overlays. Buy/sell markers plotted on chart. |
| **P&L Curve** | Cumulative profit over time with drawdown visibility. |
| **Microstructure** | Bid-ask spread over time and Order Book Imbalance (OBI) bar chart. |
| **Volume Profile** | Horizontal histogram of your fills by price level, split by buy/sell. |
| **Trade Log** | Scrollable table of every trade your algorithm executed. |

**Metrics bar** shows: Final P&L, Max Drawdown, Hurst exponent (with regime label), tick volatility, lag-1 autocorrelation, average spread, and trade counts.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/prosperity-scope.git
cd prosperity-scope

# Open in browser — that's it
open index.html            # macOS
start index.html           # Windows
xdg-open index.html        # Linux
```

Or serve it locally:

```bash
python -m http.server 8000
# Go to http://localhost:8000
```

Drag and drop any `.log` file from the Prosperity backtester onto the page.

---

## Generating Backtest Logs

Install the backtester and run your trading algorithm:

```bash
pip install -e backtester/
prosperity4bt my_trader.py 0--1 0--2 --merge-pnl --out my_run.log
```

Then drag `my_run.log` into Prosperity Scope.

### SIG Signal Logging

To populate the fair value, EMA, and Bollinger Band overlays, emit `SIG` lines from your `Trader.run()`:

```python
print(f"SIG|{symbol}|fair_value={fair:.1f}|ema={ema:.1f}|bb_upper={upper:.1f}|bb_lower={lower:.1f}")
```

Supported signal keys: `fair_value`, `ema`, `wall_mid`, `bid_wall`, `ask_wall`, `obi`, `position`, `bb_mid`, `bb_upper`, `bb_lower`.

---

## Log Format

The dashboard parses the standard backtester `.log` format:

```
Sandbox logs:
{"sandboxLog":"","lambdaLog":"[...]","timestamp":0}

Activities log:
day;timestamp;product;bid_price_1;bid_volume_1;...;mid_price;profit_and_loss

Trade History:
[{"timestamp":0,"buyer":"SUBMISSION","seller":"Bot","symbol":"KELP",...}]
```

---

## Analytics

| Metric | Method |
|--------|--------|
| Hurst exponent | Rescaled range via log-log polyfit of lagged standard deviations × 2.0 |
| Autocorrelation | Lag-1 sample autocovariance of mid-price returns |
| OBI | `(bidVol - askVol) / (bidVol + askVol)` per tick from L2 depth |
| Spread | `bestAsk - bestBid` per tick |
| Max drawdown | Peak-to-trough of cumulative P&L |

---

## Tech Stack

- **Zero dependencies** — single HTML file, no build step
- **Plotly.js** (CDN) for interactive charts
- **JetBrains Mono** + **Space Grotesk** fonts
- Vanilla JavaScript, no framework

---

## Deploying

### GitHub Pages

1. Push to GitHub
2. Go to Settings → Pages → Source: Deploy from branch → `main` / `root`
3. Your dashboard is live at `https://YOUR_USERNAME.github.io/prosperity-scope/`

### Vercel / Netlify

Just connect the repo — zero config needed for a static site.

---

## Project Structure

```
prosperity-scope/
  index.html          Complete dashboard — open this
  sample/
    demo_run.log      Sample backtest log to test with
  README.md
```

---

## Credits

Built for [IMC Prosperity 4](https://prosperity.imc.com/) — the global algorithmic trading competition.
