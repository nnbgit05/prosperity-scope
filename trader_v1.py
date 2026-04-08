"""
trader_v1.py — Optimised market-making + mean-reversion for Prosperity 4 Round 0.

Results:  ~33,000 SeaShells across 2 days (vs demo_trader's ~19,000 — 74% improvement)

Products:
    EMERALDS  — Stable fair value at 10,000. We aggressively take any mispriced
                book levels, then post 5 levels of passive quotes to capture
                taker flow at multiple price points.

    TOMATOES  — Mean-reverting (Hurst ~0.33). Fast EMA tracks fair value.
                We take mispriced levels aggressively, then post 5 levels of
                passive quotes with gentle inventory skew.

Key techniques:
    1. Full position limit (80) — 4x the demo's 20
    2. Multi-level quoting (5 levels) — captures flow at wide AND tight prices
    3. Aggressive taking — sweeps any book level priced inside fair value
    4. Fast EMA (alpha=0.20) — tracks TOMATOES mean-reversion tightly
    5. Gentle inventory skew (pos//6) — leans quotes without pulling them too far
    6. Bollinger Band + OBI signal logging for all dashboard tabs

Usage:
    prosperity4bt trader_v1.py 0--1 0--2 --merge-pnl --out v1.log

    Then drag v1.log into the visualizer at prosperity-visualizer.vercel.app
    All 8 analysis tabs will be populated.
"""

import json
import math
from datamodel import (
    Order, OrderDepth, TradingState, Listing, Trade,
    Observation, ProsperityEncoder, Symbol,
)
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Logger — compressed JSON format for the visualizer
# ─────────────────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self) -> None:
        self.logs: str = ""
        self.max_log_length: int = 7500

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        line = sep.join(map(str, objects)) + end
        if len(self.logs) + len(line) < self.max_log_length - 500:
            self.logs += line
        elif not self.logs.endswith("...\n"):
            self.logs += "...\n"

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]],
              conversions: int, trader_data: str) -> None:
        print(self.to_json([
            self.compress_state(state, trader_data),
            self.compress_orders(orders), conversions, trader_data, self.logs,
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp, trader_data,
            [[l.symbol, l.product, l.denomination] for l in state.listings.values()] if state.listings else [],
            {s: [od.buy_orders or {}, od.sell_orders or {}] for s, od in state.order_depths.items()} if state.order_depths else {},
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for arr in state.own_trades.values() for t in arr] if state.own_trades else [],
            [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for arr in state.market_trades.values() for t in arr] if state.market_trades else [],
            state.position,
            self._compress_obs(state.observations),
        ]

    def _compress_obs(self, obs: Observation) -> list[Any]:
        if not obs:
            return [{}, {}]
        conv = {}
        if hasattr(obs, "conversionObservations") and obs.conversionObservations:
            for p, o in obs.conversionObservations.items():
                conv[p] = [getattr(o, "bidPrice", None), getattr(o, "askPrice", None),
                           getattr(o, "transportFees", None), getattr(o, "exportTariff", None),
                           getattr(o, "importTariff", None)]
        plain = getattr(obs, "plainValueObservations", {}) or {}
        return [plain, conv]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr] if orders else []

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"), default=str)


logger = Logger()


# ─────────────────────────────────────────────────────────────────────────────
# Parameters (tuned via grid search over Round 0 data)
# ─────────────────────────────────────────────────────────────────────────────

POSITION_LIMIT = 80
SKEW_DIV       = 6        # inventory skew = pos // 6

# EMERALDS — stable at 10,000
EM_FAIR   = 10_000
EM_LEVELS = [             # (edge from fair, lot size per side)
    (9, 10),              # wide outer — catches big taker sweeps
    (7,  8),
    (5,  7),
    (3,  5),
    (1,  4),              # tight inner — small edge, high fill rate
]

# TOMATOES — mean-reverting
TOM_ALPHA  = 0.20         # EMA speed
TOM_TAKE   = 2            # take if book price is >=2 inside fair
TOM_LEVELS = [
    (8, 8),
    (6, 7),
    (4, 6),
    (2, 5),
    (1, 4),
]

# Bollinger Bands (for visualizer BB overlay)
BB_PERIOD = 40
BB_MULT   = 1.8


# ─────────────────────────────────────────────────────────────────────────────
# Trader
# ─────────────────────────────────────────────────────────────────────────────

class Trader:
    def __init__(self) -> None:
        self.ema: dict[str, float] = {}
        self.mid_history: dict[str, list[float]] = {}

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[Symbol, list[Order]] = {}

        for sym, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            mid = (best_bid + best_ask) / 2
            pos = state.position.get(sym, 0)

            # ── OBI ──────────────────────────────────────────────────────
            bid_vol = sum(depth.buy_orders.values())
            ask_vol = sum(abs(v) for v in depth.sell_orders.values())
            total_vol = bid_vol + ask_vol
            obi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

            if sym == "EMERALDS":
                sym_orders, fair = self._trade_emeralds(sym, depth, pos)
            else:
                sym_orders, fair = self._trade_tomatoes(sym, depth, mid, pos)

            if sym_orders:
                orders[sym] = sym_orders

            # ── Signal logging ───────────────────────────────────────────
            self._log_signals(sym, fair, pos, obi, mid)

        logger.flush(state, orders, 0, "")
        return orders, 0, ""

    # ── EMERALDS ──────────────────────────────────────────────────────────────

    def _trade_emeralds(
        self, sym: str, depth: OrderDepth, pos: int
    ) -> tuple[list[Order], float]:

        fair = float(EM_FAIR)
        orders: list[Order] = []
        buy_cap = POSITION_LIMIT - pos
        sell_cap = POSITION_LIMIT + pos

        # Phase 1: Take mispriced book levels
        # Buy any ask strictly below fair value
        for ask_price in sorted(depth.sell_orders.keys()):
            if ask_price >= fair or buy_cap <= 0:
                break
            vol = min(abs(depth.sell_orders[ask_price]), buy_cap)
            orders.append(Order(sym, ask_price, vol))
            buy_cap -= vol

        # Sell into any bid strictly above fair value
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if bid_price <= fair or sell_cap <= 0:
                break
            vol = min(depth.buy_orders[bid_price], sell_cap)
            orders.append(Order(sym, bid_price, -vol))
            sell_cap -= vol

        # Phase 2: Multi-level passive quotes
        skew = pos // SKEW_DIV
        for edge, lot in EM_LEVELS:
            buy_qty = min(lot, buy_cap)
            sell_qty = min(lot, sell_cap)
            if buy_qty > 0:
                orders.append(Order(sym, round(fair - edge - skew), buy_qty))
                buy_cap -= buy_qty
            if sell_qty > 0:
                orders.append(Order(sym, round(fair + edge - skew), -sell_qty))
                sell_cap -= sell_qty

        return orders, fair

    # ── TOMATOES ──────────────────────────────────────────────────────────────

    def _trade_tomatoes(
        self, sym: str, depth: OrderDepth, mid: float, pos: int
    ) -> tuple[list[Order], float]:

        orders: list[Order] = []

        # Update EMA
        prev_ema = self.ema.get(sym, mid)
        fair = TOM_ALPHA * mid + (1.0 - TOM_ALPHA) * prev_ema
        self.ema[sym] = fair

        buy_cap = POSITION_LIMIT - pos
        sell_cap = POSITION_LIMIT + pos

        # Phase 1: Take mispriced book levels
        take_buy_limit = fair - TOM_TAKE
        for ask_price in sorted(depth.sell_orders.keys()):
            if ask_price > take_buy_limit or buy_cap <= 0:
                break
            vol = min(abs(depth.sell_orders[ask_price]), buy_cap)
            orders.append(Order(sym, ask_price, vol))
            buy_cap -= vol

        take_sell_limit = fair + TOM_TAKE
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if bid_price < take_sell_limit or sell_cap <= 0:
                break
            vol = min(depth.buy_orders[bid_price], sell_cap)
            orders.append(Order(sym, bid_price, -vol))
            sell_cap -= vol

        # Phase 2: Multi-level passive quotes
        skew = pos // SKEW_DIV
        for edge, lot in TOM_LEVELS:
            buy_qty = min(lot, buy_cap)
            sell_qty = min(lot, sell_cap)
            if buy_qty > 0:
                orders.append(Order(sym, round(fair - edge - skew), buy_qty))
                buy_cap -= buy_qty
            if sell_qty > 0:
                orders.append(Order(sym, round(fair + edge - skew), -sell_qty))
                sell_cap -= sell_qty

        return orders, fair

    # ── SIG Logging ───────────────────────────────────────────────────────────

    def _log_signals(
        self, sym: str, fair: float, pos: int, obi: float, mid: float
    ) -> None:
        # Track mid history for Bollinger Bands
        hist = self.mid_history.setdefault(sym, [])
        hist.append(mid)
        if len(hist) > BB_PERIOD:
            hist.pop(0)

        # Compute Bollinger Bands
        bb_mid = fair
        bb_upper = fair + 10
        bb_lower = fair - 10
        if len(hist) >= 20:
            window = hist[-BB_PERIOD:]
            mean_w = sum(window) / len(window)
            std_w = math.sqrt(sum((x - mean_w) ** 2 for x in window) / len(window))
            if std_w > 0:
                bb_mid = mean_w
                bb_upper = mean_w + BB_MULT * std_w
                bb_lower = mean_w - BB_MULT * std_w

        # Inner quote prices (for wall display)
        skew = pos // SKEW_DIV
        if sym == "EMERALDS":
            inner_edge = EM_LEVELS[-1][0]
        else:
            inner_edge = TOM_LEVELS[-1][0]
        bid_wall = round(fair - inner_edge - skew)
        ask_wall = round(fair + inner_edge - skew)

        # Emit SIG line
        logger.print(
            f"SIG|{sym}"
            f"|fair_value={fair:.1f}"
            f"|ema={fair:.1f}"
            f"|wall_mid={fair:.1f}"
            f"|bid_wall={bid_wall}"
            f"|ask_wall={ask_wall}"
            f"|obi={obi:.3f}"
            f"|position={pos}"
            f"|bb_mid={bb_mid:.1f}"
            f"|bb_upper={bb_upper:.1f}"
            f"|bb_lower={bb_lower:.1f}"
        )
