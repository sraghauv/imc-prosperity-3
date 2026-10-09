from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Tuple
import jsonpickle

# Define the product names we use.
class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"

# Set default parameters for RAINFOREST_RESIN.
PARAMS = {
    Product.RAINFOREST_RESIN: {
        "fair_value": 10000,
        "take_width": 1.5,         # the minimum price deviation at which to aggressively "take" orders
        "clear_width": 0,        # width used for clearing (flattening) positions
        "disregard_edge": 1,     # disregards orders within this edge when joining or pennying
        "join_edge": 3,          # joins orders if the edge is within this amount
        "default_edge": 2,       # default edge to use if there are no levels to penny/join
        "soft_position_limit": 30,  # used for adjusting quotes in make_orders
    }
}

class Trader:
    def __init__(self, params: Dict = None):
        if params is None:
            params = PARAMS
        self.params = params
        # Define position limits for RAINFOREST_RESIN.
        self.LIMIT = {Product.RAINFOREST_RESIN: 50}

    def take_best_orders(
        self,
        product: str,
        fair_value: int,
        take_width: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
    ) -> Tuple[int, int]:
        """Attempt to take orders from the order book if prices are sufficiently mispriced."""
        position_limit = self.LIMIT[product]

        # Look at sell orders (for buying opportunity).
        if len(order_depth.sell_orders) != 0:
            best_ask = min(order_depth.sell_orders.keys())
            # In the order book, sell order volumes are stored as negative.
            best_ask_amount = -1 * order_depth.sell_orders[best_ask]
            if not prevent_adverse or abs(best_ask_amount) <= adverse_volume:
                if best_ask <= fair_value - take_width:
                    # Maximum quantity to buy is limited by available volume and remaining capacity.
                    quantity = min(best_ask_amount, position_limit - position)
                    if quantity > 0:
                        orders.append(Order(product, best_ask, quantity))
                        buy_order_volume += quantity
                        order_depth.sell_orders[best_ask] += quantity
                        if order_depth.sell_orders[best_ask] == 0:
                            del order_depth.sell_orders[best_ask]

        # Look at buy orders (for selling opportunity).
        if len(order_depth.buy_orders) != 0:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            if not prevent_adverse or abs(best_bid_amount) <= adverse_volume:
                if best_bid >= fair_value + take_width:
                    # Maximum quantity to sell is limited by available volume and our current position.
                    quantity = min(best_bid_amount, position_limit + position)
                    if quantity > 0:
                        orders.append(Order(product, best_bid, -quantity))
                        sell_order_volume += quantity
                        order_depth.buy_orders[best_bid] -= quantity
                        if order_depth.buy_orders[best_bid] == 0:
                            del order_depth.buy_orders[best_bid]

        return buy_order_volume, sell_order_volume

    def market_make(
        self,
        product: str,
        orders: List[Order],
        bid: int,
        ask: int,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> Tuple[int, int]:
        """Place passive market-making orders using calculated bid and ask quotes."""
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, round(bid), buy_quantity))  # Buy order
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, round(ask), -sell_quantity))  # Sell order
        return buy_order_volume, sell_order_volume

    def clear_position_order(
        self,
        product: str,
        fair_value: float,
        width: int,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> Tuple[List[Order], int, int]:
        """
        Attempt to flatten your position by taking orders close to fair value.
        """
        position_after_take = position + buy_order_volume - sell_order_volume
        fair_for_bid = round(fair_value - width)
        fair_for_ask = round(fair_value + width)

        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)

        if position_after_take > 0:
            # Aggregate volume from all buy orders with price greater than or equal to fair_for_ask.
            clear_quantity = sum(
                volume for price, volume in order_depth.buy_orders.items() if price >= fair_for_ask
            )
            clear_quantity = min(clear_quantity, position_after_take)
            sent_quantity = min(sell_quantity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(product, fair_for_ask, -abs(sent_quantity)))
                sell_order_volume += abs(sent_quantity)

        if position_after_take < 0:
            # Aggregate volume from all sell orders with price lower than or equal to fair_for_bid.
            clear_quantity = sum(
                abs(volume)
                for price, volume in order_depth.sell_orders.items() if price <= fair_for_bid
            )
            clear_quantity = min(clear_quantity, abs(position_after_take))
            sent_quantity = min(buy_quantity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(product, fair_for_bid, abs(sent_quantity)))
                buy_order_volume += abs(sent_quantity)

        return orders, buy_order_volume, sell_order_volume

    def take_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        take_width: float,
        position: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
    ) -> Tuple[List[Order], int, int]:
        """Aggregate orders from aggressively taking opportunities off the order book."""
        orders: List[Order] = []
        buy_order_volume = 0
        sell_order_volume = 0

        buy_order_volume, sell_order_volume = self.take_best_orders(
            product,
            fair_value,
            take_width,
            orders,
            order_depth,
            position,
            buy_order_volume,
            sell_order_volume,
            prevent_adverse,
            adverse_volume,
        )
        return orders, buy_order_volume, sell_order_volume

    def clear_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        clear_width: float,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> Tuple[List[Order], int, int]:
        """Aggregate orders aimed at flattening an imbalanced position."""
        orders: List[Order] = []
        orders, buy_order_volume, sell_order_volume = self.clear_position_order(
            product,
            fair_value,
            clear_width,
            orders,
            order_depth,
            position,
            buy_order_volume,
            sell_order_volume,
        )
        return orders, buy_order_volume, sell_order_volume

    def make_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        disregard_edge: float,
        join_edge: float,
        default_edge: float,
        manage_position: bool = False,
        soft_position_limit: int = 0,
    ) -> Tuple[List[Order], int, int]:
        """
        Creates market-making orders:
          - Adjusts bid and ask prices based on the order book and fair value.
          - Optionally adjusts quotes further if your current position is imbalanced.
        """
        orders: List[Order] = []
        asks_above_fair = [
            price for price in order_depth.sell_orders.keys() if price > fair_value + disregard_edge
        ]
        bids_below_fair = [
            price for price in order_depth.buy_orders.keys() if price < fair_value - disregard_edge
        ]

        best_ask_above_fair = min(asks_above_fair) if asks_above_fair else None
        best_bid_below_fair = max(bids_below_fair) if bids_below_fair else None

        # Set ask price.
        ask = round(fair_value + default_edge)
        if best_ask_above_fair is not None:
            if abs(best_ask_above_fair - fair_value) <= join_edge:
                ask = best_ask_above_fair
            else:
                ask = best_ask_above_fair - 1

        # Set bid price.
        bid = round(fair_value - default_edge)
        if best_bid_below_fair is not None:
            if abs(fair_value - best_bid_below_fair) <= join_edge:
                bid = best_bid_below_fair
            else:
                bid = best_bid_below_fair + 1

        if manage_position:
            if position > soft_position_limit:
                ask -= 1
            elif position < -soft_position_limit:
                bid += 1

        buy_order_volume, sell_order_volume = self.market_make(
            product,
            orders,
            bid,
            ask,
            position,
            buy_order_volume,
            sell_order_volume,
        )
        return orders, buy_order_volume, sell_order_volume

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        """
        The main entry point: for RAINFOREST_RESIN, we process the following phases:
          1. Aggressively take mispriced orders.
          2. Clear any imbalanced position.
          3. Place market-making orders.
        Any persistent internal state is stored as traderData.
        """
        traderObject = {}
        if state.traderData is not None and state.traderData != "":
            traderObject = jsonpickle.decode(state.traderData)

        result: Dict[str, List[Order]] = {}
        product = Product.RAINFOREST_RESIN

        if product in self.params and product in state.order_depths:
            resin_position = state.position.get(product, 0)
            # Phase 1: Aggressively take orders.
            resin_take_orders, buy_order_volume, sell_order_volume = self.take_orders(
                product,
                state.order_depths[product],
                self.params[product]["fair_value"],
                self.params[product]["take_width"],
                resin_position,
            )
            # Phase 2: Clear (flatten) orders.
            resin_clear_orders, buy_order_volume, sell_order_volume = self.clear_orders(
                product,
                state.order_depths[product],
                self.params[product]["fair_value"],
                self.params[product]["clear_width"],
                resin_position,
                buy_order_volume,
                sell_order_volume,
            )
            # Phase 3: Market making orders.
            resin_make_orders, _, _ = self.make_orders(
                product,
                state.order_depths[product],
                self.params[product]["fair_value"],
                resin_position,
                buy_order_volume,
                sell_order_volume,
                self.params[product]["disregard_edge"],
                self.params[product]["join_edge"],
                self.params[product]["default_edge"],
                True,
                self.params[product]["soft_position_limit"],
            )
            result[product] = resin_take_orders + resin_clear_orders + resin_make_orders

        conversions = 1
        traderData = jsonpickle.encode(traderObject)
        return result, conversions, traderData
