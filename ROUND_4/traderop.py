from typing import Any, Optional
import json
import math
import numpy as np
from math import log, sqrt
from statistics import NormalDist
from datamodel import OrderDepth, TradingState, Order, Symbol, Listing, Observation, Trade, ProsperityEncoder


# ═══════════════════════════════════════════════════════════════
# LOGGER
# ═══════════════════════════════════════════════════════════════

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([self.compress_state(state, ""), self.compress_orders(orders), conversions, "", ""]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp, trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
                for arr in trades.values() for t in arr]

    def compress_observations(self, observations: Observation) -> list[Any]:
        co = {}
        for p, o in observations.conversionObservations.items():
            co[p] = [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex]
        return [observations.plainValueObservations, co]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi, out = 0, min(len(value), max_length), ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            if len(json.dumps(candidate)) <= max_length:
                out = candidate; lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()


# ═══════════════════════════════════════════════════════════════
# BLACK-SCHOLES UTILITIES
# ═══════════════════════════════════════════════════════════════

class BlackScholes:
    @staticmethod
    def call(spot: float, strike: float, tte: float, vol: float) -> float:
        """European call price."""
        if tte <= 1e-9:
            return max(spot - strike, 0.0)
        d1 = (log(spot / strike) + 0.5 * vol * vol * tte) / (vol * sqrt(tte))
        d2 = d1 - vol * sqrt(tte)
        return spot * NormalDist().cdf(d1) - strike * NormalDist().cdf(d2)

    @staticmethod
    def delta(spot: float, strike: float, tte: float, vol: float) -> float:
        """Option delta (\u2202C/\u2202S)."""
        if tte <= 1e-9:
            return 1.0 if spot > strike else 0.0
        d1 = (log(spot / strike) + 0.5 * vol * vol * tte) / (vol * sqrt(tte))
        return NormalDist().cdf(d1)

    @staticmethod
    def gamma(spot: float, strike: float, tte: float, vol: float) -> float:
        """Option gamma (\u2202\u00b2C/\u2202S\u00b2)."""
        if tte <= 1e-9 or vol <= 0:
            return 0.0
        d1 = (log(spot / strike) + 0.5 * vol * vol * tte) / (vol * sqrt(tte))
        return NormalDist().pdf(d1) / (spot * vol * sqrt(tte))

    @staticmethod
    def implied_vol(call_price: float, spot: float, strike: float, tte: float,
                    max_iter: int = 100, tol: float = 1e-8) -> Optional[float]:
        """Implied volatility via bisection."""
        intrinsic = max(spot - strike, 0.0)
        if call_price <= intrinsic + 0.05:
            return None
        if tte <= 1e-9:
            return None
        lo, hi = 0.001, 5.0
        for _ in range(max_iter):
            mid = (lo + hi) / 2.0
            est = BlackScholes.call(spot, strike, tte, mid)
            diff = est - call_price
            if abs(diff) < tol:
                break
            if diff > 0:
                hi = mid
            else:
                lo = mid
        result = (lo + hi) / 2.0
        return result if 0.01 < result < 4.0 else None


# ═══════════════════════════════════════════════════════════════
# TRADER
# ═══════════════════════════════════════════════════════════════

class Trader:

    def __init__(self):
        # ── Position limits ───────────────────────────────────────
        self.VEV_LIMIT       = 200
        self.VOUCHER_LIMIT   = 300
        self.HYDROGEL_LIMIT  = 200

        # ── VEV Options: round-specific TTE ──────────────────────
        # ★ SET THIS EACH ROUND ★
        #   Round 1 \u2192 7,  Round 2 \u2192 6,  Round 3 \u2192 5,  Round 4 \u2192 4
        self.VEV_DAYS_LEFT = 4

        # Vouchers to actively trade (skip deep-ITM 4000/4500 and
        # far-OTM/worthless 6000/6500)
        self.VEV_STRIKES  = [5000, 5100, 5200, 5300, 5400, 5500]
        self.VEV_VOUCHERS = [f"VEV_{k}" for k in self.VEV_STRIKES]

        # Rolling IV window (smoothed estimate of market-implied vol)
        self.VEV_IV_WINDOW   = 20
        self.VEV_FALLBACK_IV = 0.26   # 26% \u2014 calibrated from sample data

        # Timestamps per year (each tick = 100 ms, 10 000 ticks/day)
        self.TICKS_PER_YEAR = 252e6

        # Spot price history
        self.vev_spot_hist: list[float] = []

        # Per-voucher implied vol history
        self.vev_iv_hist: dict[str, list[float]] = {v: [] for v in self.VEV_VOUCHERS}

        # Per-tick order counters (reset every run() call)
        self.vev_spot_buys    = 0
        self.vev_spot_sells   = 0
        self.vev_vchr_buys:  dict[str, int] = {v: 0 for v in self.VEV_VOUCHERS}
        self.vev_vchr_sells: dict[str, int] = {v: 0 for v in self.VEV_VOUCHERS}
        
        self.hydrogel_buys   = 0
        self.hydrogel_sells  = 0

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _mid(self, ob: OrderDepth) -> Optional[float]:
        if ob.buy_orders and ob.sell_orders:
            return (max(ob.buy_orders) + min(ob.sell_orders)) / 2.0
        return None

    def _best_ask(self, ob: OrderDepth) -> Optional[int]:
        return min(ob.sell_orders) if ob.sell_orders else None

    def _best_bid(self, ob: OrderDepth) -> Optional[int]:
        return max(ob.buy_orders) if ob.buy_orders else None

    def _pos(self, state: TradingState, product: str) -> int:
        return state.position.get(product, 0)

    def _vev_tte(self, state: TradingState) -> float:
        """Time-to-expiry in years at current timestamp."""
        return max((self.VEV_DAYS_LEFT / 252.0) - state.timestamp / self.TICKS_PER_YEAR, 1e-7)

    def _vev_iv(self, voucher: str) -> float:
        hist = self.vev_iv_hist[voucher]
        return float(np.mean(hist)) if hist else self.VEV_FALLBACK_IV

    # ─────────────────────────────────────────────────────────────
    # Step 1 \u2014 Update spot & IV history
    # ─────────────────────────────────────────────────────────────

    def _update_vev_data(self, state: TradingState) -> None:
        """Refresh rolling spot price and implied-vol estimates."""
        vev_ob = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if vev_ob is None:
            return
        spot = self._mid(vev_ob)
        if spot is None:
            return

        self.vev_spot_hist.append(spot)
        self.vev_spot_hist = self.vev_spot_hist[-200:]

        tte = self._vev_tte(state)
        for voucher in self.VEV_VOUCHERS:
            ob = state.order_depths.get(voucher)
            if ob is None:
                continue
            vmid = self._mid(ob)
            if vmid is None:
                continue
            strike = int(voucher.split("_")[-1])
            iv = BlackScholes.implied_vol(vmid, spot, strike, tte)
            if iv is not None:
                self.vev_iv_hist[voucher].append(iv)
                self.vev_iv_hist[voucher] = self.vev_iv_hist[voucher][-self.VEV_IV_WINDOW:]

    # ─────────────────────────────────────────────────────────────
    # Step 2 \u2014 Long-Gamma: buy options, delta-hedge spot
    # ─────────────────────────────────────────────────────────────

    def _trade_vev_options(self, state: TradingState, orders: dict) -> None:
        if not self.vev_spot_hist:
            return

        spot = self.vev_spot_hist[-1]
        tte  = self._vev_tte(state)

        # ── Compute greeks for every voucher ─────────────────────
        voucher_info = []
        for voucher in self.VEV_VOUCHERS:
            ob = state.order_depths.get(voucher)
            if ob is None or not ob.sell_orders:
                continue
            strike = int(voucher.split("_")[-1])
            iv     = self._vev_iv(voucher)
            fv     = BlackScholes.call(spot, strike, tte, iv)
            delta  = BlackScholes.delta(spot, strike, tte, iv)
            gamma  = BlackScholes.gamma(spot, strike, tte, iv)

            if delta < 1e-6:
                continue

            efficiency = gamma / delta  # gamma per unit of hedge capacity
            voucher_info.append((efficiency, voucher, ob, strike, iv, fv, delta, gamma))

        # Sort descending by efficiency \u2014 fill most efficient first
        voucher_info.sort(key=lambda x: -x[0])

        # ── Track total (signed) delta we're building this tick ───
        book_delta = 0.0
        for v in self.VEV_VOUCHERS:
            pos = self._pos(state, v)
            if pos == 0:
                continue
            strike = int(v.split("_")[-1])
            iv     = self._vev_iv(v)
            book_delta += BlackScholes.delta(spot, strike, tte, iv) * pos

        # Budget: we'll hedge with VEV, so cap net delta at VEV_LIMIT
        vev_pos     = self._pos(state, "VELVETFRUIT_EXTRACT")
        hedge_used  = -vev_pos  # how much hedge we've "spent" already
        hedge_cap   = self.VEV_LIMIT  # max units of VEV we can short

        for (eff, voucher, ob, strike, iv, fv, delta, gamma) in voucher_info:

            cur_pos  = self._pos(state, voucher)
            head_buy = self.VOUCHER_LIMIT - cur_pos - self.vev_vchr_buys[voucher]
            if head_buy <= 0:
                continue

            best_ask = self._best_ask(ob)
            if best_ask is None:
                continue

            ask_vol = abs(ob.sell_orders[best_ask])

            # How much additional delta would buying 1 unit create?
            remaining_hedge = hedge_cap - hedge_used

            # Maximum we can buy without exceeding hedge budget
            if delta > 0:
                max_by_hedge = int(remaining_hedge / delta)
            else:
                max_by_hedge = head_buy

            take_size = min(head_buy, ask_vol, max(max_by_hedge, 0))

            if take_size <= 0:
                # Can't buy more, but post a tiny passive bid to accumulate slowly
                passive_bid = int(math.floor(fv)) - 1
                if ob.buy_orders and passive_bid <= max(ob.buy_orders):
                    continue  # don't undercut existing bid
                if passive_bid > 0 and head_buy > 0:
                    # orders[voucher].append(Order(voucher, passive_bid, 1))
                    self.vev_vchr_buys[voucher] += 1
                continue

            # ── Aggressive take at best ask ───────────────────────
            if best_ask <= math.ceil(fv) + 1:
                # orders[voucher].append(Order(voucher, best_ask, take_size))
                self.vev_vchr_buys[voucher] += take_size
                book_delta  += delta * take_size
                hedge_used  += delta * take_size
                head_buy    -= take_size

            # ── Passive bid for remaining capacity ────────────────
            if head_buy > 0:
                remaining_hedge2 = hedge_cap - hedge_used
                max_by_hedge2    = int(remaining_hedge2 / delta) if delta > 0 else head_buy
                passive_size     = min(head_buy, max(max_by_hedge2, 0))
                passive_bid      = int(math.floor(fv))

                if passive_size > 0:
                    # orders[voucher].append(Order(voucher, passive_bid, passive_size))
                    self.vev_vchr_buys[voucher] += passive_size
                    book_delta += delta * passive_size
                    hedge_used += delta * passive_size

        # ── Unwind if IV spikes above 32% (vol mean-reversion exit) ───
        for voucher in self.VEV_VOUCHERS:
            cur_pos = self._pos(state, voucher)
            if cur_pos <= 0:
                continue
            iv = self._vev_iv(voucher)
            if iv < 0.32:
                continue
            ob = state.order_depths.get(voucher)
            if ob is None:
                continue
            best_bid = self._best_bid(ob)
            if best_bid is None:
                continue
            strike = int(voucher.split("_")[-1])
            fv     = BlackScholes.call(spot, strike, tte, iv)
            if best_bid >= math.floor(fv) - 1:
                sell_size = min(cur_pos - self.vev_vchr_sells[voucher],
                                abs(ob.buy_orders[best_bid]))
                if sell_size > 0:
                    # orders[voucher].append(Order(voucher, best_bid, -sell_size))
                    self.vev_vchr_sells[voucher] += sell_size
                    delta = BlackScholes.delta(spot, strike, tte, iv)
                    book_delta  -= delta * sell_size
                    hedge_used  -= delta * sell_size

        # ── Delta hedge with VELVETFRUIT_EXTRACT ─────────────────
        self._vev_delta_hedge(state, orders, book_delta)

    def _vev_delta_hedge(self, state: TradingState, orders: dict, book_delta: float) -> None:
        """Trade VEV spot to neutralise the net option delta."""
        ob = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if ob is None or not ob.buy_orders or not ob.sell_orders:
            return

        vev_pos      = self._pos(state, "VELVETFRUIT_EXTRACT")
        target_pos   = -int(round(book_delta))  # want this in VEV spot
        target_pos   = max(-self.VEV_LIMIT, min(self.VEV_LIMIT, target_pos))
        adjustment   = target_pos - vev_pos - self.vev_spot_buys + self.vev_spot_sells

        best_ask = min(ob.sell_orders)
        best_bid = max(ob.buy_orders)

        if adjustment > 0:
            buy_cap  = self.VEV_LIMIT - vev_pos - self.vev_spot_buys
            buy_size = min(adjustment, max(buy_cap, 0))
            if buy_size > 0:
                orders["VELVETFRUIT_EXTRACT"].append(Order("VELVETFRUIT_EXTRACT", best_ask, buy_size))
                self.vev_spot_buys += buy_size

        elif adjustment < 0:
            sell_cap  = self.VEV_LIMIT + vev_pos - self.vev_spot_sells
            sell_size = min(-adjustment, max(sell_cap, 0))
            if sell_size > 0:
                orders["VELVETFRUIT_EXTRACT"].append(Order("VELVETFRUIT_EXTRACT", best_bid, -sell_size))
                self.vev_spot_sells += sell_size

    # ─────────────────────────────────────────────────────────────
    # Step 3 — HYDROGEL_PACK: Mark 14 signal execution
    # ─────────────────────────────────────────────────────────────

    def _trade_hydrogel(self, state: TradingState, orders: dict) -> None:
        product = "HYDROGEL_PACK"
        position = self._pos(state, product)
        
        # Track expected position across multiple signal trades in this timestamp
        current_expected_pos = position
        
        for trade in state.market_trades.get(product, []):
            m14_buy_signal = False
            m14_sell_signal = False

            if trade.quantity in [2, 3]:
                if trade.buyer == "Mark 14":
                    m14_buy_signal = True
                if trade.seller == "Mark 14":
                    m14_sell_signal = True
                
                if m14_buy_signal:
                    # Buy up to 20 units, but don't exceed the absolute limit of 200
                    buy_vol = min(20, self.HYDROGEL_LIMIT - current_expected_pos - self.hydrogel_buys)
                    if buy_vol > 0:
                        orders[product].append(Order(product, int(round(trade.price - 1)), int(buy_vol)))
                        self.hydrogel_buys += buy_vol
                        current_expected_pos += buy_vol

                elif m14_sell_signal:
                    # Sell up to 20 units, but don't exceed the absolute limit of -200
                    sell_vol = min(20, self.HYDROGEL_LIMIT + current_expected_pos - self.hydrogel_sells)
                    if sell_vol > 0:
                        orders[product].append(Order(product, int(round(trade.price + 1)), -int(sell_vol)))
                        self.hydrogel_sells += sell_vol
                        current_expected_pos -= sell_vol

    # ─────────────────────────────────────────────────────────────
    # RUN (main entry point)
    # ─────────────────────────────────────────────────────────────

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:

        # ── Init order dict for VEV and Vouchers ─────────
        orders: dict[str, list[Order]] = {p: [] for p in state.order_depths}

        # ── Reset per-tick counters ────────────────────────────────
        self.vev_spot_buys  = 0
        self.vev_spot_sells = 0
        self.vev_vchr_buys  = {v: 0 for v in self.VEV_VOUCHERS}
        self.vev_vchr_sells = {v: 0 for v in self.VEV_VOUCHERS}
        self.hydrogel_buys  = 0
        self.hydrogel_sells = 0

        # ── Update data (must come first) ─────────────────────────
        self._update_vev_data(state)

        # ── Execute strategies ────────────────────────────────────
        self._trade_vev_options(state, orders)
        self._trade_hydrogel(state, orders)

        logger.flush(state, orders, 0, "")
        return orders, 0, ""
