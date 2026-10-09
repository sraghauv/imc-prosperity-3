from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Any
import numpy as np
import math

# Single product definition
class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"

# Parameters for rainforest resin only
PARAMS = {
    Product.RAINFOREST_RESIN: {
        "fair_value": 10000,
        "take_width": 1,
        "clear_width": 0,
        "disregard_edge": 1,
        "join_edge": 2,
        "default_edge": 4,
        "soft_position_limit": 30,
        "stop_loss_threshold": 50,
    }
}

class Trader:
    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or PARAMS
        self.LIMIT = {Product.RAINFOREST_RESIN: 20}
        self.price_history = {Product.RAINFOREST_RESIN: []}

    def get_moving_average(self, product: str, window_size: int = 400) -> float:
        history = self.price_history[product]
        if not history:
            return self.params[product]["fair_value"]
        return float(np.mean(history[-window_size:]))

    def update_price_history(self, product: str, order_depth: OrderDepth):
        if order_depth.buy_orders and order_depth.sell_orders:
            best_bid = max(order_depth.buy_orders)
            best_ask = min(order_depth.sell_orders)
            mid_price = (best_bid + best_ask) / 2
            self.price_history[product].append(mid_price)
            if len(self.price_history[product]) > 400:
                self.price_history[product].pop(0)

    def apply_stop_loss(self, product: str, order_depth: OrderDepth, fair_value: float, position: int) -> List[Order]:
        orders: List[Order] = []
        threshold = self.params[product]["stop_loss_threshold"]
        if position > 0 and order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid < fair_value - threshold:
                orders.append(Order(product, best_bid, -position))
        elif position < 0 and order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask > fair_value + threshold:
                orders.append(Order(product, best_ask, -position))
        return orders

    def take_best_orders(self, product: str, fair_value: float, take_width: float, orders: List[Order],
                         order_depth: OrderDepth, position: int, buy_vol: int, sell_vol: int) -> (int, int):
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if best_ask <= fair_value - take_width:
                qty = min(best_ask_amount, self.LIMIT[product] - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_vol += qty
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            best_bid_amount = order_depth.buy_orders[best_bid]
            if best_bid >= fair_value + take_width:
                qty = min(best_bid_amount, self.LIMIT[product] + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_vol += qty
        return buy_vol, sell_vol

    def clear_position_order(self, product: str, fair_value: float, width: float, orders: List[Order],
                             order_depth: OrderDepth, position: int, buy_vol: int, sell_vol: int) -> (int, int):
        pos_after = position + buy_vol - sell_vol
        fair_bid = round(fair_value - width)
        fair_ask = round(fair_value + width)
        if pos_after > 0 and order_depth.buy_orders:
            qty = sum(v for p, v in order_depth.buy_orders.items() if p >= fair_ask)
            qty = min(qty, pos_after)
            if qty > 0:
                orders.append(Order(product, fair_ask, -qty))
                sell_vol += qty
        elif pos_after < 0 and order_depth.sell_orders:
            qty = sum(-v for p, v in order_depth.sell_orders.items() if p <= fair_bid)
            qty = min(qty, -pos_after)
            if qty > 0:
                orders.append(Order(product, fair_bid, qty))
                buy_vol += qty
        return buy_vol, sell_vol

    def market_make(self, product: str, orders: List[Order], bid: float, ask: float,
                    position: int, buy_vol: int, sell_vol: int) -> (int, int):
        buy_qty = self.LIMIT[product] - (position + buy_vol)
        if buy_qty > 0:
            orders.append(Order(product, bid, buy_qty))
            buy_vol += buy_qty
        sell_qty = self.LIMIT[product] + (position - sell_vol)
        if sell_qty > 0:
            orders.append(Order(product, ask, -sell_qty))
            sell_vol += sell_qty
        return buy_vol, sell_vol

    def make_orders(self, product: str, order_depth: OrderDepth, fair_value: float,
                    position: int, buy_vol: int, sell_vol: int, disregard_edge: float,
                    join_edge: float, default_edge: float, manage_position: bool = True,
                    soft_limit: int = 0) -> (List[Order], int, int):
        orders: List[Order] = []
        asks = [p for p in order_depth.sell_orders if p > fair_value + disregard_edge]
        bids = [p for p in order_depth.buy_orders if p < fair_value - disregard_edge]
        ask = min(asks) if asks else round(fair_value + default_edge)
        bid = max(bids) if bids else round(fair_value - default_edge)
        if manage_position:
            pos_after = position + buy_vol - sell_vol
            if pos_after > soft_limit:
                ask += 1
            elif pos_after < -soft_limit:
                bid -= 1
        buy_vol, sell_vol = self.market_make(product, orders, bid, ask, position, buy_vol, sell_vol)
        return orders, buy_vol, sell_vol

    def run(self, state: TradingState) -> (Dict[str, List[Order]], int, str):
        results: Dict[str, List[Order]] = {}
        if Product.RAINFOREST_RESIN in state.order_depths:
            od = state.order_depths[Product.RAINFOREST_RESIN]
            pos = state.position.get(Product.RAINFOREST_RESIN, 0)
            self.update_price_history(Product.RAINFOREST_RESIN, od)
            fair = self.get_moving_average(Product.RAINFOREST_RESIN)
            buy_vol = sell_vol = 0
            orders = self.apply_stop_loss(Product.RAINFOREST_RESIN, od, fair, pos)
            if not orders:
                orders_list: List[Order] = []
                buy_vol, sell_vol = self.take_best_orders(
                    Product.RAINFOREST_RESIN, fair, self.params[Product.RAINFOREST_RESIN]["take_width"],
                    orders_list, od, pos, buy_vol, sell_vol
                )
                buy_vol, sell_vol = self.clear_position_order(
                    Product.RAINFOREST_RESIN, fair, self.params[Product.RAINFOREST_RESIN]["clear_width"],
                    orders_list, od, pos, buy_vol, sell_vol
                )
                mk_orders, buy_vol, sell_vol = self.make_orders(
                    Product.RAINFOREST_RESIN, od, fair, pos,
                    buy_vol, sell_vol,
                    self.params[Product.RAINFOREST_RESIN]["disregard_edge"],
                    self.params[Product.RAINFOREST_RESIN]["join_edge"],
                    self.params[Product.RAINFOREST_RESIN]["default_edge"],
                    True, self.params[Product.RAINFOREST_RESIN]["soft_position_limit"]
                )
                orders = orders_list + mk_orders
            results[Product.RAINFOREST_RESIN] = orders
        return results, 0, state.traderData
