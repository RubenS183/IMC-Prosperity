from typing import Any, Optional
import json

from datamodel import (
    Listing,
    Observation,
    Order,
    OrderDepth,
    ProsperityEncoder,
    Symbol,
    Trade,
    TradingState,
)


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(
        self,
        state: TradingState,
        orders: dict[Symbol, list[Order]],
        conversions: int,
        trader_data: str,
    ) -> None:
        base_length = len(
            self.to_json(
                [self.compress_state(state, ""), self.compress_orders(orders), conversions, "", ""]
            )
        )
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[listing.symbol, listing.product, listing.denomination] for listing in listings.values()]

    def compress_order_depths(
        self, order_depths: dict[Symbol, OrderDepth]
    ) -> dict[Symbol, list[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [
            [trade.symbol, trade.price, trade.quantity, trade.buyer, trade.seller, trade.timestamp]
            for trade_list in trades.values()
            for trade in trade_list
        ]

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]
        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[order.symbol, order.price, order.quantity] for order_list in orders.values() for order in order_list]

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
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()


class Trader:
    HYDROGEL_LIMIT = 200
    VOUCHER_LIMIT = 200
    DIRECTIONAL_VOUCHER_LIMIT = 80
    HYDRO_SIGNAL_QTYS = {2, 3}
    VOUCHER_STRIKES = (5200, 5300, 5400, 5500)

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

    def _default_data(self) -> dict[str, Any]:
        return {"vf_fast": None, "vf_prev": None}

    def _load_data(self, raw: str) -> dict[str, Any]:
        data = self._default_data()
        if not raw:
            return data

        try:
            decoded = json.loads(raw)
        except Exception:
            return data

        if isinstance(decoded, dict):
            if "vf_fast" in decoded:
                data["vf_fast"] = decoded["vf_fast"]
            if "vf_prev" in decoded:
                data["vf_prev"] = decoded["vf_prev"]
        return data

    def _dump_data(self, data: dict[str, Any]) -> str:
        return json.dumps(data, separators=(",", ":"))

    def _update_vf_state(self, spot: float, data: dict[str, Any]) -> tuple[float, Optional[float]]:
        prev_spot = data.get("vf_prev")
        fast = data.get("vf_fast")
        if fast is None:
            fast = spot
        else:
            fast = 0.18 * spot + 0.82 * float(fast)

        data["vf_fast"] = fast
        data["vf_prev"] = spot
        return fast, float(prev_spot) if prev_spot is not None else None

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

        # Sample-data winner logic: only small Mark 14 prints are informative,
        # and crossing the 16-tick Hydrogel spread destroys the edge.
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
                logger.print(
                    f"HYDRO BUY signal qty={trade.quantity} trade={trade.price} quote={price}"
                )

            elif trade.seller == "Mark 14":
                qty = min(20, self.HYDROGEL_LIMIT + expected_pos)
                if qty <= 0:
                    continue
                price = self._inside_ask(best_bid, best_ask, int(trade.price) + 1)
                orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, -qty))
                expected_pos -= qty
                reacted = True
                logger.print(
                    f"HYDRO SELL signal qty={trade.quantity} trade={trade.price} quote={price}"
                )

        # If we still carry inventory without a fresh signal, lean toward flat.
        if reacted or pos == 0:
            return

        mid = self._mid(depth)
        if mid is None:
            return

        if pos > 0:
            price = self._inside_ask(best_bid, best_ask, int(round(mid)) + 1)
            orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, -min(20, pos)))
            logger.print(f"HYDRO unwind long quote={price} size={min(20, pos)}")
        else:
            price = self._inside_bid(best_bid, best_ask, int(round(mid)) - 1)
            orders["HYDROGEL_PACK"].append(Order("HYDROGEL_PACK", price, min(20, -pos)))
            logger.print(f"HYDRO unwind short quote={price} size={min(20, -pos)}")

    def trade_vouchers(
        self,
        state: TradingState,
        orders: dict[str, list[Order]],
        data: dict[str, Any],
    ) -> None:
        depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if depth is None:
            return

        spot = self._mid(depth)
        if spot is None:
            return

        fast, prev_spot = self._update_vf_state(spot, data)
        bearish_regime = spot < fast - 4 and (prev_spot is None or spot <= prev_spot)
        for strike in self.VOUCHER_STRIKES:
            symbol = f"VEV_{strike}"
            voucher_depth = state.order_depths.get(symbol)
            if voucher_depth is None or not voucher_depth.buy_orders:
                continue

            pos = self._pos(state, symbol)
            best_bid = max(voucher_depth.buy_orders)
            best_ask = min(voucher_depth.sell_orders) if voucher_depth.sell_orders else None
            otm_amount = strike - spot
            limit = self.DIRECTIONAL_VOUCHER_LIMIT if strike == 5200 else self.VOUCHER_LIMIT

            if strike != 5200 and pos < 0 and best_ask is not None and otm_amount < 12:
                qty = min(20, abs(pos))
                orders[symbol].append(Order(symbol, best_ask, qty))
                logger.print(
                    f"{symbol} cover quote={best_ask} qty={qty} spot={spot:.1f}"
                )
                continue

            # The sample data consistently rewards shorting these vouchers once
            # they are meaningfully OTM, but only while the bid still has value.
            should_short = False
            base_qty = 0
            if strike == 5200:
                should_short = (
                    best_bid > 0
                    and bearish_regime
                    and state.timestamp >= 20000
                    and spot < 5276
                )
                base_qty = 2
            else:
                if strike == 5300:
                    should_short = best_bid > 0 and (otm_amount > 20 or (bearish_regime and otm_amount > 15))
                    base_qty = 8 if bearish_regime else 5
                else:
                    should_short = otm_amount > 20 and best_bid > 0
                    base_qty = 10

            if should_short and pos > -limit:
                qty = min(base_qty, limit + pos)
                if qty > 0:
                    orders[symbol].append(Order(symbol, best_bid, -qty))
                    logger.print(
                        f"{symbol} short quote={best_bid} qty={qty} spot={spot:.1f} otm={otm_amount:.1f}"
                    )

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[str, list[Order]] = {symbol: [] for symbol in state.order_depths}
        data = self._load_data(state.traderData)

        self.trade_hydrogel(state, orders)
        self.trade_vouchers(state, orders, data)

        trader_data = self._dump_data(data)
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
