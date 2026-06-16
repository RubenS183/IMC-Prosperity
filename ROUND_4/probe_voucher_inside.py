from typing import Optional

from datamodel import Order, OrderDepth, Symbol, TradingState


class Trader:
    # Tiny dummy probe: quote one tick above the best bid when the voucher is
    # OTM. If this still fills in the official log, the production strategy can
    # improve its sell price instead of sitting directly on the bid.
    PROBE_LIMIT = 8
    PROBE_STRIKES = (5200, 5300, 5400, 5500)

    def _pos(self, state: TradingState, symbol: str) -> int:
        return state.position.get(symbol, 0)

    def _mid(self, depth: OrderDepth) -> Optional[float]:
        if depth.buy_orders and depth.sell_orders:
            return (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        return None

    def _inside_sell_price(self, depth: OrderDepth) -> Optional[int]:
        if not depth.buy_orders:
            return None

        best_bid = max(depth.buy_orders)
        if not depth.sell_orders:
            return best_bid

        best_ask = min(depth.sell_orders)
        if best_bid + 1 < best_ask:
            return best_bid + 1
        return best_bid

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[str, list[Order]] = {symbol: [] for symbol in state.order_depths}
        depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if depth is None:
            return orders, 0, ""

        spot = self._mid(depth)
        if spot is None:
            return orders, 0, ""

        for strike in self.PROBE_STRIKES:
            if strike == 5200 and state.timestamp < 35000:
                continue

            symbol = f"VEV_{strike}"
            voucher_depth = state.order_depths.get(symbol)
            if voucher_depth is None:
                continue

            if strike - spot <= 20:
                continue

            pos = self._pos(state, symbol)
            if pos <= -self.PROBE_LIMIT:
                continue

            price = self._inside_sell_price(voucher_depth)
            if price is not None and price > 0:
                orders[symbol].append(Order(symbol, price, -1))

        return orders, 0, ""
