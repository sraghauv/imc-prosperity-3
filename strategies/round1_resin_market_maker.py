from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle

# Define a Product class for available products.
class Product:
    RESIN = "RAINFOREST_RESIN"

# Set up parameters for our stable product.
PARAMS = {
    Product.RESIN: {
        "fair_value": 10000,
        "take_width": 1,
        "clear_width": 0,
        # default_edge acts like our market-making spread.
        "default_edge": 4,
        "soft_position_limit": 30,
        # Visible portion for iceberg orders.
        "iceberg_visible": 4,
    },
}

class Trader:
    def __init__(self, params=None):
        if params is None:
            params = PARAMS
        self.params = params
        self.LIMIT = {Product.RESIN: self.params[Product.RESIN]["soft_position_limit"]}
        # Dictionary to hold any hidden (iceberg) volume per product and side.
        # Structure: { product: {"buy": remaining_buy_volume, "sell": remaining_sell_volume} }
        self.iceberg_orders = {}

    def take_orders(
        self, product: str, order_depth: OrderDepth, fair_value: int, take_width: float, position: int
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_order_volume = 0
        sell_order_volume = 0
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_volume = order_depth.sell_orders[best_ask]
            if best_ask < fair_value - take_width:
                quantity = min(-best_ask_volume, self.LIMIT[product] - position)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_volume = order_depth.buy_orders[best_bid]
            if best_bid > fair_value + take_width:
                quantity = min(best_bid_volume, self.LIMIT[product] + position)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity
        return orders, buy_order_volume, sell_order_volume

    def clear_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: int,
        clear_width: int,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        position_after = position + buy_order_volume - sell_order_volume
        fair_bid = fair_value - clear_width
        fair_ask = fair_value + clear_width
        if position_after > 0:
            # Sell orders to reduce a long position.
            for price, volume in order_depth.buy_orders.items():
                if price >= fair_ask:
                    quantity = min(volume, position_after)
                    orders.append(Order(product, price, -quantity))
                    sell_order_volume += quantity
                    position_after -= quantity
                    if position_after <= 0:
                        break
        elif position_after < 0:
            # Buy orders to cover a short position.
            for price, volume in order_depth.sell_orders.items():
                if price <= fair_bid:
                    quantity = min(-volume, -position_after)
                    orders.append(Order(product, price, quantity))
                    buy_order_volume += quantity
                    position_after += quantity
                    if position_after >= 0:
                        break
        return orders, buy_order_volume, sell_order_volume

    def make_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: int,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        default_edge: float,
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        position_after = position + buy_order_volume - sell_order_volume
        mm_bid = fair_value - default_edge
        mm_ask = fair_value + default_edge
        iceberg_visible = self.params[product].get("iceberg_visible", 5)
        
        # Process a market-making buy order.
        buy_qty = self.LIMIT[product] - position_after
        if buy_qty > 0:
            if buy_qty > iceberg_visible:
                visible_qty = iceberg_visible
                remainder = buy_qty - visible_qty
                # Record the hidden volume for the buy side.
                if product not in self.iceberg_orders:
                    self.iceberg_orders[product] = {"buy": 0, "sell": 0}
                self.iceberg_orders[product]["buy"] += remainder
            else:
                visible_qty = buy_qty
            orders.append(Order(product, mm_bid, visible_qty))
            buy_order_volume += visible_qty

        # Process a market-making sell order.
        sell_qty = self.LIMIT[product] + position_after
        if sell_qty > 0:
            if sell_qty > iceberg_visible:
                visible_qty = iceberg_visible
                remainder = sell_qty - visible_qty
                if product not in self.iceberg_orders:
                    self.iceberg_orders[product] = {"buy": 0, "sell": 0}
                self.iceberg_orders[product]["sell"] += remainder
            else:
                visible_qty = sell_qty
            orders.append(Order(product, mm_ask, -visible_qty))
            sell_order_volume += visible_qty

        return orders, buy_order_volume, sell_order_volume

    def replenish_iceberg_orders(self, product: str, fair_value: int) -> List[Order]:
        """
        On subsequent calls, this function reissues the visible portion of any hidden (iceberg) orders.
        """
        orders: List[Order] = []
        if product not in self.iceberg_orders:
            return orders
        iceberg_visible = self.params[product].get("iceberg_visible", 5)
        default_edge = self.params[product]["default_edge"]
        
        # For buy-side iceberg orders.
        if self.iceberg_orders[product]["buy"] > 0:
            qty = min(iceberg_visible, self.iceberg_orders[product]["buy"])
            orders.append(Order(product, fair_value - default_edge, qty))
            self.iceberg_orders[product]["buy"] -= qty
        # For sell-side iceberg orders.
        if self.iceberg_orders[product]["sell"] > 0:
            qty = min(iceberg_visible, self.iceberg_orders[product]["sell"])
            orders.append(Order(product, fair_value + default_edge, -qty))
            self.iceberg_orders[product]["sell"] -= qty
        
        return orders

    def run(self, state: TradingState):
        traderObject = {}
        if state.traderData is not None and state.traderData != "":
            traderObject = jsonpickle.decode(state.traderData)
        result = {}
        product = Product.RESIN
        if product in state.order_depths:
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            fair_value = self.params[product]["fair_value"]
            take_width = self.params[product]["take_width"]
            clear_width = self.params[product]["clear_width"]
            default_edge = self.params[product]["default_edge"]

            take_orders_list, buy_order_volume, sell_order_volume = self.take_orders(
                product, order_depth, fair_value, take_width, position
            )
            clear_orders_list, buy_order_volume, sell_order_volume = self.clear_orders(
                product, order_depth, fair_value, clear_width, position, buy_order_volume, sell_order_volume
            )
            make_orders_list, buy_order_volume, sell_order_volume = self.make_orders(
                product, order_depth, fair_value, position, buy_order_volume, sell_order_volume, default_edge
            )
            # Replenish any outstanding iceberg orders from previous rounds.
            iceberg_orders_list = self.replenish_iceberg_orders(product, fair_value)
            
            # Combine all orders.
            orders = take_orders_list + clear_orders_list + make_orders_list + iceberg_orders_list
            result[product] = orders

        conversions = 0
        traderData = jsonpickle.encode(traderObject)
        return result, conversions, traderData