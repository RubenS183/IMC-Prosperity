from typing import Any, Optional, List, Dict, Tuple
import json
import math
from datamodel import (
    OrderDepth, TradingState, Order, Symbol,
    Listing, Observation, Trade, ProsperityEncoder,
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
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(
        self, order_depths: dict[Symbol, OrderDepth]
    ) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [
            [t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp]
            for arr in trades.values()
            for t in arr
        ]

    def compress_observations(self, observations: Observation) -> list[Any]:
        co = {}
        for p, o in observations.conversionObservations.items():
            co[p] = [
                o.bidPrice, o.askPrice, o.transportFees,
                o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex,
            ]
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
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()

class Trader:
    DECAY_RATE = 0.80

    def __init__(self):
        self.signal_state = {
            'HYDROGEL_PACK': 0.0,
            'VF_SUPPORT': 0.0,
            'VF_FADE': 0.0
        }
        self._td_loaded = False

    def _pos(self, state: TradingState, sym: str) -> int:
        return state.position.get(sym, 0)

    def _mid(self, ob: OrderDepth) -> Optional[float]:
        if ob.buy_orders and ob.sell_orders:
            return (max(ob.buy_orders) + min(ob.sell_orders)) / 2.0
        return None

    def load_trader_data(self, state: TradingState):
        try:
            td = json.loads(state.traderData) if state.traderData else {}
            self.signal_state = td.get("signals", self.signal_state)
        except Exception:
            pass
        self._td_loaded = True

    def save_trader_data(self) -> str:
        return json.dumps({
            "signals": self.signal_state,
        })

    def update_signals(self, state: TradingState):
        for k in self.signal_state:
            self.signal_state[k] *= self.DECAY_RATE

        for sym, trades_list in state.market_trades.items():
            for t in trades_list:
                buyer, seller = t.buyer, t.seller
                if sym == 'HYDROGEL_PACK':
                    if seller == 'Mark 14':
                        self.signal_state['HYDROGEL_PACK'] = -1.0
                        logger.print(f"SIGNAL: Mark 14 SELL HYDROGEL at {t.timestamp}")
                    elif buyer == 'Mark 14':
                        self.signal_state['HYDROGEL_PACK'] = 1.0
                        logger.print(f"SIGNAL: Mark 14 BUY HYDROGEL at {t.timestamp}")

                if sym == 'VELVETFRUIT_EXTRACT':
                    if buyer == 'Mark 67':
                        self.signal_state['VF_SUPPORT'] = 1.0
                        logger.print(f"SIGNAL: Mark 67 BUY VF at {t.timestamp}")
                    if seller == 'Mark 49':
                        self.signal_state['VF_FADE'] = 1.0
                        logger.print(f"SIGNAL: Mark 49 SELL VF at {t.timestamp}")
                    if buyer == 'Mark 55':
                        self.signal_state['VF_FADE'] = -1.0
                        logger.print(f"SIGNAL: Mark 55 BUY VF at {t.timestamp}")

    def trade_hydrogel(self, state: TradingState, orders: dict[str, list[Order]]):
        sig = self.signal_state.get('HYDROGEL_PACK', 0.0)
        pos = self._pos(state, 'HYDROGEL_PACK')
        ob = state.order_depths.get('HYDROGEL_PACK')
        if not ob or not ob.buy_orders or not ob.sell_orders: return

        mid = self._mid(ob)
        bid = max(ob.buy_orders)
        ask = min(ob.sell_orders)

        target_pos = 0
        if sig < -0.35: target_pos = -45
        elif sig > 0.35: target_pos = 45

        diff = target_pos - pos
        if diff < 0:
            qty = max(diff, -abs(ob.buy_orders[bid])) # take what we can
            orders['HYDROGEL_PACK'].append(Order('HYDROGEL_PACK', bid, qty))
            logger.print(f"TRADE: HYDROGEL SELL qty={qty} price={bid} sig={sig:.2f} pos={pos}->{pos+qty}")
        elif diff > 0:
            qty = min(diff, abs(ob.sell_orders[ask]))
            orders['HYDROGEL_PACK'].append(Order('HYDROGEL_PACK', ask, qty))
            logger.print(f"TRADE: HYDROGEL BUY qty={qty} price={ask} sig={sig:.2f} pos={pos}->{pos+qty}")
            
    def trade_options(self, state: TradingState, orders: dict[str, list[Order]]):
        vf_ob = state.order_depths.get('VELVETFRUIT_EXTRACT')
        if not vf_ob: return
        vf_spot = self._mid(vf_ob)
        if not vf_spot: return

        for strike in [5300, 5400, 5500]:
            sym = f"VEV_{strike}"
            ob = state.order_depths.get(sym)
            if not ob or not ob.buy_orders: continue
            
            pos = self._pos(state, sym)
            otm_amt = strike - vf_spot

            # Sell OTM
            if otm_amt > 20 and pos > -200:
                bid = max(ob.buy_orders)
                qty = min(10, 200 + pos)
                orders[sym].append(Order(sym, bid, -qty))
                logger.print(f"TRADE: {sym} SHORT qty={qty} price={bid} spot={vf_spot} otm={otm_amt}")
            
            # Stop-loss (buy back) if spot rallies
            if otm_amt < 10 and pos < 0:
                ask = min(ob.sell_orders) if ob.sell_orders else strike - vf_spot + 1
                qty = min(10, abs(pos))
                orders[sym].append(Order(sym, int(ask), qty))
                logger.print(f"TRADE: {sym} EXIT qty={qty} price={ask} spot={vf_spot} otm={otm_amt}")

    def trade_velvetfruit(self, state: TradingState, orders: dict[str, list[Order]]):
        pos = self._pos(state, 'VELVETFRUIT_EXTRACT')
        ob = state.order_depths.get('VELVETFRUIT_EXTRACT')
        if not ob or not ob.buy_orders or not ob.sell_orders: return

        mid = self._mid(ob)
        bid = max(ob.buy_orders)
        ask = min(ob.sell_orders)

        support_sig = self.signal_state.get('VF_SUPPORT', 0.0)
        fade_sig = self.signal_state.get('VF_FADE', 0.0)
        
        target_pos = 0
        if support_sig > 0.5 and 5254 <= mid <= 5268:
            target_pos = 45
        elif fade_sig < -0.5 or mid >= 5292:
            target_pos = -45
        elif fade_sig > 0.5:
            target_pos = 45

        diff = target_pos - pos
        if diff < 0:
            qty = max(diff, -abs(ob.buy_orders[bid]))
            orders['VELVETFRUIT_EXTRACT'].append(Order('VELVETFRUIT_EXTRACT', bid, qty))
            logger.print(f"TRADE: VF SELL qty={qty} price={bid} sup={support_sig:.2f} fade={fade_sig:.2f} pos={pos}->{pos+qty}")
        elif diff > 0:
            qty = min(diff, abs(ob.sell_orders[ask]))
            orders['VELVETFRUIT_EXTRACT'].append(Order('VELVETFRUIT_EXTRACT', ask, qty))
            logger.print(f"TRADE: VF BUY qty={qty} price={ask} sup={support_sig:.2f} fade={fade_sig:.2f} pos={pos}->{pos+qty}")

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        orders: dict[str, list[Order]] = {p: [] for p in state.order_depths}
        if not self._td_loaded: self.load_trader_data(state)

        self.update_signals(state)
        self.trade_hydrogel(state, orders)
        self.trade_options(state, orders)
        self.trade_velvetfruit(state, orders)

        td = self.save_trader_data()
        logger.flush(state, orders, 0, td)
        return orders, 0, td
