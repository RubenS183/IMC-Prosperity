from typing import Any, Optional
import json

from datamodel import Order, OrderDepth, Symbol, TradingState


class Trader:
    HYDROGEL_LIMIT = 200
    VELVET_LIMIT = 200
    VOUCHER_LIMIT = 300

    HYDRO_SIGNAL_QTYS = {2, 3}
    RICH_ENTRY_UNTIL = 10000
    TRAIL_AFTER = 150000

    RICH_VELVET_MIN_BID = 5296
    FALLBACK_VELVET_MIN_BID = 5265

    RICH_VOUCHER_MIN_BID = {
        4000: 1287,
        4500: 789,
        5000: 296,
        5100: 202,
        5200: 120,
        5300: 58,
        5400: 20,
        5500: 7,
    }
    FALLBACK_VOUCHER_MIN_BID = {
        4000: 1260,
        4500: 760,
        5000: 265,
        5100: 170,
        5200: 95,
        5300: 48,
        5400: 20,
        5500: 6,
    }
    VOUCHER_TRAIL_REBOUND = {
        4000: 45,
        4500: 35,
        5000: 20,
        5100: 16,
        5200: 12,
        5300: 8,
        5400: 4,
        5500: 2,
    }
    VOUCHER_STRIKES = (4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500)

    def _pos(self, state: TradingState, symbol: str) -> int:
        return state.position.get(symbol, 0)

    def _mid(self, depth: OrderDepth) -> Optional[float]:
        if depth.buy_orders and depth.sell_orders:
            return (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        return None

    def _load_data(self, raw: str) -> dict[str, Any]:
        if not raw:
            return {"lows": {}, "stopped": {}}
        try:
            data = json.loads(raw)
        except Exception:
            return {"lows": {}, "stopped": {}}
        if not isinstance(data, dict):
            return {"lows": {}, "stopped": {}}
        data.setdefault("lows", {})
        data.setdefault("stopped", {})
        return data

    def _dump_data(self, data: dict[str, Any]) -> str:
        return json.dumps(data, separators=(",", ":"))

    def _best_bid_ask(self, depth: OrderDepth) -> tuple[Optional[int], Optional[int]]:
        bid = max(depth.buy_orders) if depth.buy_orders else None
        ask = min(depth.sell_orders) if depth.sell_orders else None
        return bid, ask

    def _inside_bid(self, best_bid: int, best_ask: int, desired_price: int) -> int:
        if best_bid + 1 < best_ask:
            return max(best_bid + 1, min(best_ask - 1, desired_price))
        return best_bid

    def _inside_ask(self, best_bid: int, best_ask: int, desired_price: int) -> int:
        if best_bid + 1 < best_ask:
            return min(best_ask - 1, max(best_bid + 1, desired_price))
        return best_ask

    def _sell_bid_ladder(
        self,
        orders: dict[str, list[Order]],
        symbol: str,
        depth: OrderDepth,
        capacity: int,
        min_price: int,
    ) -> None:
        remaining = capacity
        for price in sorted((p for p in depth.buy_orders if p >= min_price), reverse=True):
            qty = min(remaining, depth.buy_orders[price])
            if qty <= 0:
                continue
            orders[symbol].append(Order(symbol, price, -qty))
            remaining -= qty
            if remaining <= 0:
                return

    def _buy_ask_ladder(
        self,
        orders: dict[str, list[Order]],
        symbol: str,
        depth: OrderDepth,
        capacity: int,
    ) -> None:
        remaining = capacity
        for price in sorted(depth.sell_orders):
            qty = min(remaining, abs(depth.sell_orders[price]))
            if qty <= 0:
                continue
            orders[symbol].append(Order(symbol, price, qty))
            remaining -= qty
            if remaining <= 0:
                return

    def _entry_min_bid(self, strike: int, timestamp: int) -> int:
        if timestamp <= self.RICH_ENTRY_UNTIL:
            return self.RICH_VOUCHER_MIN_BID[strike]
        return self.FALLBACK_VOUCHER_MIN_BID[strike]

    def _update_low(self, data: dict[str, Any], symbol: str, mid: float) -> float:
        lows = data["lows"]
        old = lows.get(symbol)
        if old is None or mid < float(old):
            lows[symbol] = mid
            return mid
        return float(old)

    def trade_hydrogel(self, state: TradingState, orders: dict[str, list[Order]]) -> None:
        depth = state.order_depths.get("HYDROGEL_PACK")
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            return

        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is None or best_ask is None:
            return

        pos = self._pos(state, "HYDROGEL_PACK")
        expected_pos = pos
        reacted = False

        for trade in state.market_trades.get("HYDROGEL_PACK", []):
            if trade.quantity not in self.HYDRO_SIGNAL_QTYS:
                continue

            if trade.buyer == "Mark 14":
                qty = min(20, self.HYDROGEL_LIMIT - expected_pos)
                if qty <= 0:
                    continue
                price = self._inside_bid(best_bid, best_ask, int(trade.price) - 1)
                orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, qty))
                expected_pos += qty
                reacted = True

            elif trade.seller == "Mark 14":
                qty = min(20, self.HYDROGEL_LIMIT + expected_pos)
                if qty <= 0:
                    continue
                price = self._inside_ask(best_bid, best_ask, int(trade.price) + 1)
                orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, -qty))
                expected_pos -= qty
                reacted = True

        if reacted or pos == 0:
            return

        mid = self._mid(depth)
        if mid is None:
            return

        if pos > 0:
            price = self._inside_ask(best_bid, best_ask, int(round(mid)) + 1)
            orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, -min(20, pos)))
        else:
            price = self._inside_bid(best_bid, best_ask, int(round(mid)) - 1)
            orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, min(20, -pos)))

    def trade_velvetfruit(
        self,
        state: TradingState,
        orders: dict[str, list[Order]],
        data: dict[str, Any],
    ) -> None:
        symbol = "VELVETFRUIT_EXTRACT"
        depth = state.order_depths.get(symbol)
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            return

        spot = self._mid(depth)
        if spot is None:
            return

        pos = self._pos(state, symbol)
        low = self._update_low(data, symbol, spot)
        stopped = data["stopped"].get(symbol, False)

        if pos < 0 and state.timestamp >= self.TRAIL_AFTER and spot >= low + 35:
            self._buy_ask_ladder(orders, symbol, depth, abs(pos))
            data["stopped"][symbol] = True
            return

        if stopped:
            return

        min_bid = (
            self.RICH_VELVET_MIN_BID
            if state.timestamp <= self.RICH_ENTRY_UNTIL
            else self.FALLBACK_VELVET_MIN_BID
        )
        if pos > -self.VELVET_LIMIT:
            self._sell_bid_ladder(orders, symbol, depth, self.VELVET_LIMIT + pos, min_bid)

    def trade_vouchers(
        self,
        state: TradingState,
        orders: dict[str, list[Order]],
        data: dict[str, Any],
    ) -> None:
        for strike in self.VOUCHER_STRIKES:
            symbol = f"VEV_{strike}"
            depth = state.order_depths.get(symbol)
            if depth is None or not depth.buy_orders:
                continue

            mid = self._mid(depth)
            if mid is None:
                continue

            pos = self._pos(state, symbol)
            low = self._update_low(data, symbol, mid)
            stopped = data["stopped"].get(symbol, False)

            if (
                pos < 0
                and state.timestamp >= self.TRAIL_AFTER
                and mid >= low + self.VOUCHER_TRAIL_REBOUND[strike]
            ):
                if depth.sell_orders:
                    self._buy_ask_ladder(orders, symbol, depth, abs(pos))
                    data["stopped"][symbol] = True
                continue

            if stopped or pos <= -self.VOUCHER_LIMIT:
                continue

            self._sell_bid_ladder(
                orders,
                symbol,
                depth,
                self.VOUCHER_LIMIT + pos,
                self._entry_min_bid(strike, state.timestamp),
            )

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[str, list[Order]] = {symbol: [] for symbol in state.order_depths}
        data = self._load_data(state.traderData)

        self.trade_velvetfruit(state, orders, data)
        self.trade_vouchers(state, orders, data)
        self.trade_hydrogel(state, orders)

        return orders, 0, self._dump_data(data)
