from typing import Optional

from datamodel import Order, OrderDepth, Symbol, TradingState


class Trader:
    HYDROGEL_LIMIT = 200
    HYDRO_SIGNAL_QTYS = {2, 3}

    # Fixed-copytrader logic, but using the round-4 voucher limit from context.
    VOUCHER_LIMITS = {5300: 300, 5400: 300, 5500: 300}
    VOUCHER_QTYS = {5300: 5, 5400: 10, 5500: 10}
    VOUCHER_STRIKES = (5300, 5400, 5500)

    def _pos(self, state: TradingState, symbol: str) -> int:
        return state.position.get(symbol, 0)

    def _mid(self, depth: OrderDepth) -> Optional[float]:
        if depth.buy_orders and depth.sell_orders:
            return (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        return None

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

    def trade_vouchers(self, state: TradingState, orders: dict[str, list[Order]]) -> None:
        depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if depth is None:
            return

        spot = self._mid(depth)
        if spot is None:
            return

        for strike in self.VOUCHER_STRIKES:
            symbol = f"VEV_{strike}"
            voucher_depth = state.order_depths.get(symbol)
            if voucher_depth is None or not voucher_depth.buy_orders:
                continue

            pos = self._pos(state, symbol)
            best_bid = max(voucher_depth.buy_orders)
            best_ask = min(voucher_depth.sell_orders) if voucher_depth.sell_orders else None
            otm_amount = strike - spot
            limit = self.VOUCHER_LIMITS[strike]

            if otm_amount > 20 and best_bid > 0 and pos > -limit:
                qty = min(self.VOUCHER_QTYS[strike], limit + pos)
                if qty > 0:
                    orders[symbol].append(Order(symbol, best_bid, -qty))

            if otm_amount < 12 and pos < 0 and best_ask is not None:
                qty = min(20, abs(pos))
                if qty > 0:
                    orders[symbol].append(Order(symbol, best_ask, qty))

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[str, list[Order]] = {symbol: [] for symbol in state.order_depths}

        self.trade_hydrogel(state, orders)
        self.trade_vouchers(state, orders)

        return orders, 0, ""
