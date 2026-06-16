import math
import json
from datamodel import OrderDepth, TradingState, Order, Symbol, Listing, Observation, Trade, ProsperityEncoder
from typing import List, Any
import jsonpickle


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
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
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])
        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]
        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [trade.symbol, trade.price, trade.quantity, trade.buyer, trade.seller, trade.timestamp]
                )
        return compressed

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
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."
            encoded_candidate = json.dumps(candidate)
            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out

logger = Logger()

class Trader:
    def bid(self):
        return 25

    # ── Empirically calibrated parameters ───────────────────────────────────
    POSITION_LIMIT   = 80      # confirmed from game rules
    EMA_FAST         = 0.30    # optimal α from Step 1 sweep
    EMA_SLOW         = 0.01    # slow baseline for mean-reversion signal
    SKEW_STRENGTH    = 3     # ticks/unit inventory ratio (soft, linear)
    OBI_SKEW         = 2     # ticks/unit OBI → quote center shift
    OBI_AGGR_THRESH  = 0.55    # OBI threshold for inventory-unwind takes
    UNWIND_THRESH    = 60      # positions beyond this trigger OBI-timed unwind
    DEV_THRESH       = 3.5     # EMA deviation ticks for mean-reversion take
    PASSIVE_QTY      = 20      # passive quote size
    AGGR_QTY         = 15      # aggressive order size
    MM_HALF_SPREAD   = 7       # half-spread from fair value for passive quotes
    #                            (bots sit at ±8 → we get priority at ±7)

    # ── Entry point ─────────────────────────────────────────────────────────
    def run(self, state: TradingState):
        try:
            trader_state = jsonpickle.decode(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        result = {}
        for product, order_depth in state.order_depths.items():
            if product == "ASH_COATED_OSMIUM":
                position = state.position.get(product, 0)
        
                if not order_depth.buy_orders or not order_depth.sell_orders:
                    result[product] = []
                    continue
        
                best_bid = max(order_depth.buy_orders)
                best_ask = min(order_depth.sell_orders)
        
                # Calculate VWAP mid
                bids, asks = order_depth.buy_orders, order_depth.sell_orders
                bid_pricevolume = sum(p * v for p, v in bids.items())
                bid_volume  = sum(v for v in bids.values())
                ask_pricevolume = sum(p * abs(v) for p, v in asks.items())
                ask_volume  = sum(abs(v) for v in asks.values())
                
                weighted_midprice = None
                if bid_volume > 0 and ask_volume > 0:
                    weighted_midprice = (bid_pricevolume / bid_volume + ask_pricevolume / ask_volume) / 2
                if weighted_midprice is None:
                    weighted_midprice = (best_bid + best_ask) / 2

                # Calculate L1 OBI
                l1_buy_volume = order_depth.buy_orders[best_bid]
                l1_sell_volume = abs(order_depth.sell_orders[best_ask])
                total = l1_buy_volume + l1_sell_volume
                order_book_imbalance = (l1_buy_volume - l1_sell_volume) / total if total > 0 else 0
        
                # ── 1. Fair Value (EMA of VWAP mid, α=0.30) ─────────────────────────
                ema_f = trader_state.get("aco_ema_f", weighted_midprice)
                ema_s = trader_state.get("aco_ema_s", weighted_midprice)
                ema_f = self.EMA_FAST * weighted_midprice + (1.0 - self.EMA_FAST) * ema_f
                ema_s = self.EMA_SLOW * weighted_midprice + (1.0 - self.EMA_SLOW) * ema_s
                trader_state["aco_ema_f"] = ema_f
                trader_state["aco_ema_s"] = ema_s
        
                fair_value  = ema_f           # best estimate of fair price
                deviation = fair_value - ema_s      # + = overbought (fast > slow), − = oversold
        
        
                # ── 3. Passive Quote Construction ────────────────────────────────────
                #   Shift quote center by OBI (lean into expected direction) and
                #   inventory ratio (discourage building further one-sided position).
                inv_ratio = position / self.POSITION_LIMIT   # in [-1, +1]
                # Inventory skew: push quotes away from current position
                # OBI skew: lean quotes toward expected price direction
                quote_ctr = fair_value - self.SKEW_STRENGTH * inv_ratio + self.OBI_SKEW * order_book_imbalance
        
                passive_bid = min(round(quote_ctr) - self.MM_HALF_SPREAD,  best_bid + 1)
                passive_ask = max(round(quote_ctr) + self.MM_HALF_SPREAD,  best_ask - 1)
        
                # Safety: never let quotes cross
                if passive_bid >= passive_ask:
                    passive_bid = round(fair_value) - 1
                    passive_ask = round(fair_value) + 1
        
                orders: List[Order] = []
                buy_room  = self.POSITION_LIMIT - position   # remaining buy capacity
                sell_room = self.POSITION_LIMIT + position   # remaining sell capacity
        
                # ── LAYER 1: Mean Reversion Takes ────────────────────────────────────
                #   The market strongly mean-reverts (momentum corr = −0.47).
                #   When fast EMA deviates from slow EMA by DEV_THRESH, take liquidity.
                if deviation < -self.DEV_THRESH and buy_room > 0:
                    qty = min(self.AGGR_QTY, buy_room)
                    orders.append(Order(product, best_ask, qty))
                    buy_room -= qty

                elif deviation > self.DEV_THRESH and sell_room > 0:
                    qty = min(self.AGGR_QTY, sell_room)
                    orders.append(Order(product, best_bid, -qty))
                    sell_room -= qty
        
                # ── LAYER 2: OBI-Timed Inventory Unwind ─────────────────────────────
                #   Aggressive takes NOT used for pure directional alpha (exp. move +2
                #   ticks vs. spread cost 8 ticks → EV negative when starting neutral).
                #   BUT: when we carry large inventory + OBI aligns with our exit,
                #   taking is +EV because we save expected adverse price movement.
                if order_book_imbalance < -self.OBI_AGGR_THRESH and position > self.UNWIND_THRESH and sell_room > 0:
                    # OBI bearish + we're long → unwind longs at best bid
                    qty = min(self.AGGR_QTY, position - self.UNWIND_THRESH // 2, sell_room)
                    if qty > 0:
                        orders.append(Order(product, best_bid, -qty))
                        sell_room -= qty
        
                elif order_book_imbalance > self.OBI_AGGR_THRESH and position < -self.UNWIND_THRESH and buy_room > 0:
                    # OBI bullish + we're short → unwind shorts at best ask
                    qty = min(self.AGGR_QTY, -position - self.UNWIND_THRESH // 2, buy_room)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))
                        buy_room -= qty
        
                # ── LAYER 3: Passive Market Making ───────────────────────────────────
                #   Penny the bots (who sit at best_bid and best_ask).
                #   We get price priority → fill first when market orders arrive.
                #   Quote center already accounts for inventory + OBI skew above.
                if buy_room > 0:
                    orders.append(Order(product, passive_bid, min(self.PASSIVE_QTY, buy_room)))
        
                if sell_room > 0:
                    orders.append(Order(product, passive_ask, -min(self.PASSIVE_QTY, sell_room)))
        
                result[product] = orders

            elif product == "INTARIAN_PEPPER_ROOT":

                if not order_depth.sell_orders:
                    result[product] = []
                    continue
                
                best_ask = min(order_depth.sell_orders)
                pos = state.position.get(product, 0)
                qty = min(10, self.POSITION_LIMIT - pos)

                if qty > 0:
                    result[product] = [Order(product, best_ask, qty)]
                else:
                    result[product] = []
            else:
                result[product] = []

        trader_data_out = jsonpickle.encode(trader_state)
        conversions = 0
        logger.flush(state, result, conversions, trader_data_out)
        return result, conversions, trader_data_out