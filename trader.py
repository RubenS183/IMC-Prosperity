from datamodel import OrderDepth, TradingState, Order, Listing, Observation, Trade, ProsperityEncoder
from typing import Any, Optional
import json
import math

Symbol = str


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
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for arr in trades.values() for t in arr]

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
        if max_length <= 0:
            return ""
        if len(json.dumps(value)) <= max_length:
            return value
        return value[: max(0, max_length - 5)] + "..."


logger = Logger()


class Trader:
    LIMIT = 10
    FAST = 0.18
    SLOW = 0.018
    VAR = 0.04
    REL = 0.05
    TRADED_PREFIXES = ("SLEEP_POD_", "MICROCHIP_", "SNACKPACK_", "UV_VISOR_")
    PAIR_GROUPS = ("SNACKPACK_", "PEBBLES_")
    EXTRA_PRODUCTS = {
        "PANEL_2X4",
        "TRANSLATOR_ASTRO_BLACK",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "PEBBLES_L",
        "PEBBLES_M",
        "PEBBLES_XS",
        "PEBBLES_S",
    }
    SKIP_PRODUCTS = {
        "SLEEP_POD_LAMB_WOOL",
        "SNACKPACK_RASPBERRY",
        "UV_VISOR_RED",
    }
    MAX_POS = {
        "MICROCHIP_OVAL": 3,
        "MICROCHIP_RECTANGLE": 5,
        "MICROCHIP_TRIANGLE": 3,
        "SNACKPACK_VANILLA": 6,
        "UV_VISOR_YELLOW": 4,
        "PANEL_2X4": 5,
        "TRANSLATOR_ASTRO_BLACK": 6,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 5,
        "GALAXY_SOUNDS_BLACK_HOLES": 4,
        "GALAXY_SOUNDS_SOLAR_WINDS": 4,
        "PEBBLES_L": 3,
        "PEBBLES_M": 6,
        "PEBBLES_XS": 3,
        "PEBBLES_S": 3,
    }
    CAUTIOUS_PRODUCTS = {
        "GALAXY_SOUNDS_BLACK_HOLES",
        "MICROCHIP_OVAL",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
        "PEBBLES_S",
        "SNACKPACK_VANILLA",
        "UV_VISOR_YELLOW",
    }

    def _load(self, data: str) -> dict[str, Any]:
        if not data:
            return {"p": {}, "rel": {}, "cash": {}, "lr": {}}
        try:
            out = json.loads(data)
            if isinstance(out, dict):
                out.setdefault("p", {})
                out.setdefault("rel", {})
                out.setdefault("cash", {})
                out.setdefault("lr", {})
                return out
        except Exception:
            pass
        return {"p": {}, "rel": {}, "cash": {}, "lr": {}}

    def _mid(self, od: OrderDepth) -> Optional[float]:
        if not od.buy_orders or not od.sell_orders:
            return None
        return (max(od.buy_orders) + min(od.sell_orders)) / 2.0

    def _group_key(self, product: str) -> str:
        for prefix in self.PAIR_GROUPS:
            if product.startswith(prefix):
                return prefix
        return ""

    def _tradeable(self, product: str) -> bool:
        if product in self.SKIP_PRODUCTS:
            return False
        return product.startswith(self.TRADED_PREFIXES) or product in self.EXTRA_PRODUCTS

    def _max_pos(self, product: str) -> int:
        return self.MAX_POS.get(product, self.LIMIT)

    def _lag_edge(self, product: str, last_ret: dict[str, float]) -> float:
        if product == "SNACKPACK_VANILLA":
            return -0.55 * last_ret.get("SNACKPACK_CHOCOLATE", 0.0)
        if product == "SNACKPACK_CHOCOLATE":
            return -0.55 * last_ret.get("SNACKPACK_VANILLA", 0.0)
        if product == "SNACKPACK_STRAWBERRY":
            return 0.45 * last_ret.get("SNACKPACK_PISTACHIO", 0.0) - 0.45 * last_ret.get("SNACKPACK_RASPBERRY", 0.0)
        if product == "SNACKPACK_RASPBERRY":
            return -0.45 * last_ret.get("SNACKPACK_STRAWBERRY", 0.0) - 0.35 * last_ret.get("SNACKPACK_PISTACHIO", 0.0)
        if product == "SNACKPACK_PISTACHIO":
            return 0.35 * last_ret.get("SNACKPACK_STRAWBERRY", 0.0) - 0.30 * last_ret.get("SNACKPACK_RASPBERRY", 0.0)
        if product.startswith("PEBBLES_"):
            if product == "PEBBLES_XL":
                return -0.25 * (
                    last_ret.get("PEBBLES_L", 0.0)
                    + last_ret.get("PEBBLES_M", 0.0)
                    + last_ret.get("PEBBLES_S", 0.0)
                    + last_ret.get("PEBBLES_XS", 0.0)
                ) / 4.0
            return -0.35 * last_ret.get("PEBBLES_XL", 0.0)
        return 0.0

    def _quote(
        self,
        product: str,
        od: OrderDepth,
        fair: float,
        vol: float,
        pos: int,
        orders: list[Order],
    ) -> None:
        if not od.buy_orders or not od.sell_orders:
            return

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        spread = best_ask - best_bid
        if spread < 3:
            return

        skew = pos * max(0.35, min(2.0, vol * 0.045))
        reservation = fair - skew
        width = max(1.0, min(spread / 2.0 - 1.0, 1.5 + vol * 0.03))

        bid = min(best_bid + 1, math.floor(reservation - width))
        ask = max(best_ask - 1, math.ceil(reservation + width))
        bid = min(bid, best_ask - 1)
        ask = max(ask, best_bid + 1)

        buy_cap = self.LIMIT - pos
        sell_cap = self.LIMIT + pos
        quote_size = 2 if abs(pos) < 6 else 1

        if buy_cap > 0 and bid > 0:
            orders.append(Order(product, int(bid), min(quote_size, buy_cap)))
        if sell_cap > 0:
            orders.append(Order(product, int(ask), -min(quote_size, sell_cap)))

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        memory = self._load(state.traderData)
        pdata = memory["p"]
        rdata = memory["rel"]
        cash = memory["cash"]
        last_ret = memory["lr"]
        mids: dict[str, float] = {}

        for product, trades in state.own_trades.items():
            c = float(cash.get(product, 0.0))
            for trade in trades:
                if trade.buyer == "SUBMISSION":
                    c -= trade.price * trade.quantity
                if trade.seller == "SUBMISSION":
                    c += trade.price * trade.quantity
            cash[product] = c

        for product, od in state.order_depths.items():
            mid = self._mid(od)
            if mid is not None:
                mids[product] = mid

        group_mean: dict[str, float] = {}
        group_count: dict[str, int] = {}
        for product, mid in mids.items():
            key = self._group_key(product)
            if key:
                group_mean[key] = group_mean.get(key, 0.0) + mid
                group_count[key] = group_count.get(key, 0) + 1
        for key in group_mean:
            group_mean[key] /= group_count[key]

        result: dict[Symbol, list[Order]] = {p: [] for p in state.order_depths}

        for product, od in state.order_depths.items():
            mid = mids.get(product)
            if mid is None or not self._tradeable(product):
                continue

            raw = pdata.get(product)
            if raw is None:
                pdata[product] = {"f": mid, "s": mid, "v": 25.0, "l": mid, "n": 0}
                continue

            fast = float(raw.get("f", mid))
            slow = float(raw.get("s", mid))
            vol = max(1.0, math.sqrt(max(1.0, float(raw.get("v", 25.0)))))
            last = float(raw.get("l", mid))
            n = int(raw.get("n", 1))
            ret = mid - last

            fair = 0.72 * fast + 0.28 * slow
            if abs(ret) > 1.7 * vol:
                fair -= 0.18 * ret
            fair += self._lag_edge(product, last_ret)

            key = self._group_key(product)
            if key in group_mean:
                rel = mid - group_mean[key]
                rel_avg = float(rdata.get(product, rel))
                fair -= 0.28 * (rel - rel_avg)

            pos = state.position.get(product, 0)
            best_bid = max(od.buy_orders)
            best_ask = min(od.sell_orders)
            spread = best_ask - best_bid
            mtm = float(cash.get(product, 0.0)) + pos * mid
            product_limit = self._max_pos(product)
            max_pos = product_limit
            drawdown_width = 0.0
            if mtm < -500:
                max_pos = 0
            elif mtm < -180:
                max_pos = min(max_pos, 2)
                drawdown_width = 1.0
            elif mtm < -80:
                max_pos = min(max_pos, 4)
                drawdown_width = 0.5
            elif n < 30:
                max_pos = min(max_pos, 4)

            if max_pos == 0 and pos != 0:
                if pos > 0:
                    result[product].append(Order(product, best_bid, -pos))
                else:
                    result[product].append(Order(product, best_ask, -pos))
                continue

            cautious_width = 0.6 if product in self.CAUTIOUS_PRODUCTS else 0.0
            width = max(1.0, min(spread / 2.0 - 1.0, 1.8 + vol * 0.03 + drawdown_width + cautious_width))
            skew = pos * max(0.45, min(2.2, vol * 0.05))
            reservation = fair - skew
            bid = min(best_bid + 1, math.floor(reservation - width))
            ask = max(best_ask - 1, math.ceil(reservation + width))
            bid = min(bid, best_ask - 1)
            ask = max(ask, best_bid + 1)

            buy_cap = max(0, min(self.LIMIT - pos, product_limit - pos, max_pos - pos))
            sell_cap = max(0, min(self.LIMIT + pos, product_limit + pos, max_pos + pos))
            size = 1 if abs(pos) >= 4 or n < 80 else 2
            if buy_cap > 0 and bid > 0:
                result[product].append(Order(product, int(bid), min(size, buy_cap)))
            if sell_cap > 0:
                result[product].append(Order(product, int(ask), -min(size, sell_cap)))

        for product, mid in mids.items():
            raw = pdata.get(product, {"f": mid, "s": mid, "v": 25.0, "l": mid})
            fast = float(raw.get("f", mid))
            slow = float(raw.get("s", mid))
            var = max(1.0, float(raw.get("v", 25.0)))
            last = float(raw.get("l", mid))
            err = mid - fast
            pdata[product] = {
                "f": fast + self.FAST * (mid - fast),
                "s": slow + self.SLOW * (mid - slow),
                "v": (1.0 - self.VAR) * var + self.VAR * err * err,
                "l": mid,
                "n": min(9999, int(raw.get("n", 0)) + 1),
            }
            last_ret[product] = mid - last

            key = self._group_key(product)
            if key in group_mean:
                rel = mid - group_mean[key]
                old = float(rdata.get(product, rel))
                rdata[product] = old + self.REL * (rel - old)

        trader_data = json.dumps(memory, separators=(",", ":"))
        logger.flush(state, result, 0, trader_data)
        return result, 0, trader_data
