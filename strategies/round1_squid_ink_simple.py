from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle

# Define a Product class for available products.
class Product:
    SQUID_INK = "SQUID_INK"

# Parameter dictionary for the SQUID_INK product.
# This strategy uses a short-term mean reversion approach.
PARAMS = {
    Product.SQUID_INK: {
        "fair_value": 2000,            # Baseline fair value for SQUID_INK
        "take_width": 1,              # Price deviation threshold to trigger taking orders
        "clear_width": 0,             # Width for clearing positions (set to 0 for immediacy)
        "default_edge": 1,            # Spread used for market-making orders
        "soft_position_limit": 20,    # Maximum allowed position (absolute value)
        # Mean reversion parameters:
        "reversion_beta": 0.2,        # Reversion coefficient – higher means stronger pull back toward recent mid-price
        "prevent_adverse": True,      # Flag to avoid adverse liquidity if needed
        "adverse_volume": 20,         # Volume threshold to ignore levels that are too thin
    },
}

class Trader:
    def __init__(self, params=None):
        if params is None:
            params = PARAMS
        self.params = params
        self.LIMIT = {Product.SQUID_INK: self.params[Product.SQUID_INK]["soft_position_limit"]}

    def squid_ink_fair_value(self, order_depth: OrderDepth, traderObject: dict) -> float:
        """
        Compute the fair value for SQUID_INK using a simple mean reversion strategy.
        
        1. Compute the mid-price from the best ask and best bid.
        2. If a previous mid-price is available in traderObject (stored as "squid_last_price"),
           compute the deviation and adjust the current mid-price using the reversion coefficient.
           This adjustment represents our expectation that extreme deviations will revert.
        3. If no previous price is available, simply use the mid-price.
        """
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_ask + best_bid) / 2.0
            if traderObject.get("squid_last_price") is not None:
                last_price = traderObject["squid_last_price"]
                # Calculate the deviation from the last price.
                deviation = mid_price - last_price
                # Adjustment pulls the mid-price back toward the previous level.
                adjustment = deviation * self.params[Product.SQUID_INK]["reversion_beta"]
                fair_value = mid_price - adjustment
            else:
                fair_value = mid_price
            traderObject["squid_last_price"] = mid_price
            return fair_value
        # If order book data is missing, return the baseline fair value.
        return self.params[Product.SQUID_INK]["fair_value"]

    def take_orders(
        self, product: str, order_depth: OrderDepth, fair_value: float, take_width: float, position: int,
        prevent_adverse: bool = False, adverse_volume: int = 0,
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_order_volume = 0
        sell_order_volume = 0

        # Look at sell orders (offers to sell).
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_volume = order_depth.sell_orders[best_ask]
            # If the best ask is well below our fair value minus the take width, it is an oversold signal.
            if best_ask < fair_value - take_width:
                quantity = min(-best_ask_volume, self.LIMIT[product] - position)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_order_volume += quantity

        # Look at buy orders (bids to buy).
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_volume = order_depth.buy_orders[best_bid]
            # If the best bid is well above our fair value plus the take width, it is an overbought signal.
            if best_bid > fair_value + take_width:
                quantity = min(best_bid_volume, self.LIMIT[product] + position)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_order_volume += quantity

        return orders, buy_order_volume, sell_order_volume

    def clear_orders(
        self, product: str, order_depth: OrderDepth, fair_value: float, clear_width: float, position: int,
        buy_order_volume: int, sell_order_volume: int,
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        position_after = position + buy_order_volume - sell_order_volume
        fair_bid = fair_value - clear_width
        fair_ask = fair_value + clear_width

        if position_after > 0:
            # If long, try to sell at bid levels above fair_ask.
            for price, volume in order_depth.buy_orders.items():
                if price >= fair_ask:
                    quantity = min(volume, position_after)
                    orders.append(Order(product, price, -quantity))
                    sell_order_volume += quantity
                    position_after -= quantity
                    if position_after <= 0:
                        break
        elif position_after < 0:
            # If short, try to buy at ask levels below fair_bid.
            for price, volume in order_depth.sell_orders.items():
                if price <= fair_bid:
                    quantity = min(-volume, -position_after)
                    orders.append(Order(product, price, quantity))
                    buy_order_volume += quantity
                    position_after += quantity
                    if position_after >= 0:
                        break

        return orders, buy_order_volume, sell_order_volume

    def market_make(
        self, product: str, orders: List[Order], bid: float, ask: float,
        position: int, buy_order_volume: int, sell_order_volume: int,
    ) -> (int, int):
        # Calculate how many units we can safely buy or sell.
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, round(bid), buy_quantity))
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, round(ask), -sell_quantity))
        return buy_order_volume, sell_order_volume

    def make_orders(
        self, product: str, order_depth: OrderDepth, fair_value: float, position: int,
        buy_order_volume: int, sell_order_volume: int, default_edge: float,
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        position_after = position + buy_order_volume - sell_order_volume
        mm_bid = fair_value - default_edge
        mm_ask = fair_value + default_edge
        buy_qty = self.LIMIT[product] - position_after
        if buy_qty > 0:
            orders.append(Order(product, mm_bid, buy_qty))
            buy_order_volume += buy_qty
        sell_qty = self.LIMIT[product] + position_after
        if sell_qty > 0:
            orders.append(Order(product, mm_ask, -sell_qty))
            sell_order_volume += sell_qty
        return orders, buy_order_volume, sell_order_volume

    def run(self, state: TradingState):
        traderObject = {}
        if state.traderData:
            traderObject = jsonpickle.decode(state.traderData)
        result = {}
        product = Product.SQUID_INK
        if product in state.order_depths:
            order_depth = state.order_depths[product]
            position = state.position.get(product, 0)
            base_fair_value = self.params[product]["fair_value"]
            take_width = self.params[product]["take_width"]
            clear_width = self.params[product]["clear_width"]
            default_edge = self.params[product]["default_edge"]

            # Compute a dynamic fair value using our mean reversion strategy.
            computed_fair_value = self.squid_ink_fair_value(order_depth, traderObject)
            if computed_fair_value is None:
                computed_fair_value = base_fair_value

            # Generate orders to capture reversion signals (order taking).
            take_orders_list, buy_order_volume, sell_order_volume = self.take_orders(
                product, order_depth, computed_fair_value, take_width, position,
                self.params[product].get("prevent_adverse", False),
                self.params[product].get("adverse_volume", 0)
            )
            # Generate orders to clear unwanted positions.
            clear_orders_list, buy_order_volume, sell_order_volume = self.clear_orders(
                product, order_depth, computed_fair_value, clear_width, position,
                buy_order_volume, sell_order_volume
            )
            # Generate market-making orders at a default edge.
            make_orders_list, buy_order_volume, sell_order_volume = self.make_orders(
                product, order_depth, computed_fair_value, position,
                buy_order_volume, sell_order_volume, default_edge
            )
            result[product] = take_orders_list + clear_orders_list + make_orders_list

        conversions = 0
        traderData = jsonpickle.encode(traderObject)
        return result, conversions, traderData
