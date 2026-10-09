from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Any
import jsonpickle
import numpy as np
import math
from math import log, sqrt
from statistics import NormalDist

# ------------------------------------------------------------
# Product definitions: combine products from both files
# ------------------------------------------------------------
class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    PICNIC_BASKET1 = "PICNIC_BASKET1"
    PICNIC_BASKET2 = "PICNIC_BASKET2"
    CROISSANTS = "CROISSANTS"
    JAMS = "JAMS"
    DJEMBES = "DJEMBES"
    SQUID_INK = "SQUID_INK"
    VOLCANIC_ROCK = "VOLCANIC_ROCK"
    VOLCANIC_ROCK_VOUCHER_9500 = "VOLCANIC_ROCK_VOUCHER_9500"
    VOLCANIC_ROCK_VOUCHER_9750 = "VOLCANIC_ROCK_VOUCHER_9750"
    VOLCANIC_ROCK_VOUCHER_10000 = "VOLCANIC_ROCK_VOUCHER_10000"
    VOLCANIC_ROCK_VOUCHER_10250 = "VOLCANIC_ROCK_VOUCHER_10250"
    VOLCANIC_ROCK_VOUCHER_10500 = "VOLCANIC_ROCK_VOUCHER_10500"
    MAGNIFICENT_MACARONS = "MAGNIFICENT_MACARONS"

# ------------------------------------------------------------
# Parameters: merge the PARAMS dictionaries from both files.
# For overlapping keys, we combine the settings.
# ------------------------------------------------------------
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
    },
    Product.KELP: {
        "take_width": 1,
        "clear_width": 0,
        "prevent_adverse": True,
        "adverse_volume": 20,
        "reversion_beta": -0.229,
        "disregard_edge": 1,
        "join_edge": 0,
        "default_edge": 1,
        "stop_loss_threshold": 25,
    },
    Product.PICNIC_BASKET1: {
        "default_spread_mean": -38.2,
        "spread_std_window": 45,
        "zscore_threshold": 2.1,
        "target_position": 60,
        "basket_constituents": {
            Product.CROISSANTS: 6,
            Product.JAMS: 3,
            Product.DJEMBES: 1,
        },
    },
    Product.PICNIC_BASKET2: {
        "default_spread_mean": 76.0,
        "spread_std_window": 45,
        "zscore_threshold": 2,
        "target_position": 50,
        "basket_constituents": {
            Product.CROISSANTS: 4,
            Product.JAMS: 2,
        },
    },
    Product.SQUID_INK: {
        "take_width": 2,
        "clear_width": 1,
        "prevent_adverse": True,
        "adverse_volume": 15,
        "reversion_beta": -0.25,
        "disregard_edge": 2,
        "join_edge": 0,
        "default_edge": 0.5,
        "iceberg_peak": 8,
    },
    Product.VOLCANIC_ROCK: {
        "take_width": 2.0,
        "clear_width": 1.0,
        "disregard_edge": 0.5,
        "join_edge": 0.0,
        "default_edge": 0.5,
    },
    Product.VOLCANIC_ROCK_VOUCHER_9500: {
        "mean_volatility": 0.14,
        "strike": 9500,
        "std_window": 30,
        "zscore_threshold": 1,
    },
    Product.VOLCANIC_ROCK_VOUCHER_9750: {
        "mean_volatility": 0.15,
        "strike": 9750,
        "std_window": 30,
        "zscore_threshold": 0.4,
    },
    Product.VOLCANIC_ROCK_VOUCHER_10000: {
        "mean_volatility": 0.15,
        "strike": 10000,
        "std_window": 30,
        "zscore_threshold": 0.4,
    },
    Product.VOLCANIC_ROCK_VOUCHER_10250: {
        "mean_volatility": 0.15,
        "strike": 10250,
        "std_window": 30,
        "zscore_threshold": 1.2,
    },
    Product.VOLCANIC_ROCK_VOUCHER_10500: {
        "mean_volatility": 0.15,
        "strike": 10500,
        "std_window": 30,
        "zscore_threshold": 2.0,
    },
    Product.MAGNIFICENT_MACARONS: {
        # sugar→fair‑price multiplier
        "fair_value_multiplier": 1.0,
        # widths for take/clear logic
        "take_width": 5.0,
        "clear_width": 2.0,
        # critical sunlight index from your CSI script
        "CSI": 28.22,
        # storage cost per unit per timestamp
        "storage_cost": 0.1,
        # max conversions per run
        "conversion_limit": 10,
        "disregard_edge": 0.0,
        "join_edge":      0.0,
        "default_edge":   0.0
    }
}

# ------------------------------------------------------------
# Black-Scholes helper functions (copied as in file 2)
# ------------------------------------------------------------
class BlackScholes:
    @staticmethod
    def black_scholes_call(spot, strike, time_to_expiry, volatility):
        d1 = (log(spot) - log(strike) + 0.5 * volatility**2 * time_to_expiry) / (volatility * sqrt(time_to_expiry))
        d2 = d1 - volatility * sqrt(time_to_expiry)
        return spot * NormalDist().cdf(d1) - strike * NormalDist().cdf(d2)

    @staticmethod
    def implied_volatility(call_price, spot, strike, time_to_expiry, max_iterations=200, tolerance=1e-10):
        low_vol = 0.01
        high_vol = 1.0
        volatility = (low_vol + high_vol) / 2.0
        for _ in range(max_iterations):
            estimated_price = BlackScholes.black_scholes_call(spot, strike, time_to_expiry, volatility)
            diff = estimated_price - call_price
            if abs(diff) < tolerance:
                break
            elif diff > 0:
                high_vol = volatility
            else:
                low_vol = volatility
            volatility = (low_vol + high_vol) / 2.0
        return volatility

    @staticmethod
    def delta(spot, strike, time_to_expiry, volatility):
        d1 = (log(spot) - log(strike) + 0.5 * volatility**2 * time_to_expiry) / (volatility * sqrt(time_to_expiry))
        return NormalDist().cdf(d1)

# ------------------------------------------------------------
# Merged Trader class
# ------------------------------------------------------------
class Trader:
    def __init__(self, params: Dict = None):
        if params is None:
            params = PARAMS
        self.params = params
        # Merge the LIMITs from both files.
        self.LIMIT = {
            Product.RAINFOREST_RESIN: 20,
            Product.KELP: 20,
            Product.PICNIC_BASKET1: 60,
            Product.PICNIC_BASKET2: 100,
            Product.CROISSANTS: 250,
            Product.JAMS: 350,
            Product.DJEMBES: 60,
            Product.SQUID_INK: 4,
            Product.VOLCANIC_ROCK: 100,
            Product.VOLCANIC_ROCK_VOUCHER_9500: 0,
            Product.VOLCANIC_ROCK_VOUCHER_9750: 200,
            Product.VOLCANIC_ROCK_VOUCHER_10000: 200,
            Product.VOLCANIC_ROCK_VOUCHER_10250: 0,
            Product.VOLCANIC_ROCK_VOUCHER_10500: 200,
            Product.MAGNIFICENT_MACARONS: 75
        }
        # Additional moving average history for rainforest resin
        self.price_history = {
            Product.RAINFOREST_RESIN: []
        }
        # Basket spread history is used for PICNIC_BASKET products.
        self.spread_history = {
            Product.PICNIC_BASKET1: [],
            Product.PICNIC_BASKET2: [],
        }

    # ---------------
    # Methods from file 1 (rainforest resin moving average & basket orders)
    # ---------------
    def get_moving_average(self, product: str, window_size: int = 400) -> float:
        history = self.price_history[product]
        if not history:
            return self.params[product]["fair_value"]
        return float(np.mean(history[-window_size:]))

    def update_price_history(self, product: str, order_depth: OrderDepth):
        if order_depth.buy_orders and order_depth.sell_orders:
            mid_price = (max(order_depth.buy_orders) + min(order_depth.sell_orders)) / 2
            self.price_history[product].append(mid_price)
            if len(self.price_history[product]) > 400:
                self.price_history[product].pop(0)

    def apply_stop_loss(self, product: str, order_depth: OrderDepth, fair_value: float, position: int) -> List[Order]:
        orders: List[Order] = []
        threshold = self.params[product]["stop_loss_threshold"]
        if position > 0 and order_depth.buy_orders:
            if max(order_depth.buy_orders) < fair_value - threshold:
                orders.append(Order(product, max(order_depth.buy_orders), -position))
        elif position < 0 and order_depth.sell_orders:
            if min(order_depth.sell_orders) > fair_value + threshold:
                orders.append(Order(product, min(order_depth.sell_orders), -position))
        return orders
    
    def get_swmid(self, order_depth: OrderDepth) -> int or None:
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        best_bid_vol = abs(order_depth.buy_orders[best_bid])
        best_ask_vol = abs(order_depth.sell_orders[best_ask])
        mid = (best_bid * best_ask_vol + best_ask * best_bid_vol) / (best_bid_vol + best_ask_vol)
        return int(round(mid))

    def get_synthetic_basket_order_depth(self, constituents: Dict[str, int],
                                         order_depths: Dict[str, OrderDepth]) -> OrderDepth:
        synthetic = OrderDepth()
        bid_total = 0
        ask_total = 0
        bid_vols = []
        ask_vols = []
        for asset, weight in constituents.items():
            if asset not in order_depths:
                continue
            depth = order_depths[asset]
            best_bid = max(depth.buy_orders) if depth.buy_orders else 0
            best_ask = min(depth.sell_orders) if depth.sell_orders else float('inf')
            bid_total += best_bid * weight
            ask_total += best_ask * weight
            if depth.buy_orders and best_bid > 0:
                bid_vols.append(abs(depth.buy_orders[best_bid]) // weight)
            if depth.sell_orders and best_ask < float('inf'):
                ask_vols.append(abs(depth.sell_orders[best_ask]) // weight)
        if bid_vols:
            synthetic.buy_orders[int(round(bid_total))] = min(bid_vols)
        if ask_vols:
            synthetic.sell_orders[int(round(ask_total))] = -min(ask_vols)
        return synthetic

    def convert_synthetic_basket_orders(self, synthetic_orders: List[Order],
                                          order_depths: Dict[str, OrderDepth],
                                          constituents: Dict[str, int]) -> Dict[str, List[Order]]:
        component_orders = {asset: [] for asset in constituents.keys() if asset != Product.CROISSANTS}
        for order in synthetic_orders:
            qty = order.quantity
            if qty > 0:
                for asset, weight in constituents.items():
                    if asset == Product.CROISSANTS:
                        continue
                    if asset in order_depths and order_depths[asset].buy_orders:
                        best_bid = max(order_depths[asset].buy_orders)
                        component_orders[asset].append(Order(asset, int(round(best_bid)), -qty * weight))
            elif qty < 0:
                for asset, weight in constituents.items():
                    if asset == Product.CROISSANTS:
                        continue
                    if asset in order_depths and order_depths[asset].sell_orders:
                        best_ask = min(order_depths[asset].sell_orders)
                        component_orders[asset].append(Order(asset, int(round(best_ask)), -qty * weight))
        return component_orders

    def execute_spread_orders(self, target_position: int, basket_position: int,
                                order_depths: Dict[str, OrderDepth],
                                basket_product: str, constituents: Dict[str, int]) -> Dict[str, List[Order]]:
        basket_depth = order_depths[basket_product]
        synthetic_depth = self.get_synthetic_basket_order_depth(constituents, order_depths)
        orders_by_product = {}
        if target_position > basket_position:
            # Buying basket => sell synthetic side
            if basket_depth.sell_orders:
                best_ask = min(basket_depth.sell_orders)
                basket_volume = abs(basket_depth.sell_orders[best_ask])
            else:
                best_ask = None
                basket_volume = 0
            if synthetic_depth.buy_orders:
                best_bid_syn = max(synthetic_depth.buy_orders)
            else:
                best_bid_syn = None
            exec_volume = min(basket_volume, abs(target_position - basket_position))
            if exec_volume > 0 and best_ask is not None and best_bid_syn is not None:
                basket_order = Order(basket_product, int(round(best_ask)), exec_volume)
                synthetic_order = Order("SYNTHETIC", int(round(best_bid_syn)), -exec_volume)
                comp_orders = self.convert_synthetic_basket_orders(
                    synthetic_orders=[synthetic_order],
                    order_depths=order_depths,
                    constituents=constituents
                )
                orders_by_product[basket_product] = [basket_order]
                orders_by_product.update(comp_orders)
                return orders_by_product
        else:
            # Selling basket => buy synthetic side
            if basket_depth.buy_orders:
                best_bid = max(basket_depth.buy_orders)
                basket_volume = abs(basket_depth.buy_orders[best_bid])
            else:
                best_bid = None
                basket_volume = 0
            if synthetic_depth.sell_orders:
                best_ask_syn = min(synthetic_depth.sell_orders)
            else:
                best_ask_syn = None
            exec_volume = min(basket_volume, abs(target_position - basket_position))
            if exec_volume > 0 and best_bid is not None and best_ask_syn is not None:
                basket_order = Order(basket_product, int(round(best_bid)), -exec_volume)
                synthetic_order = Order("SYNTHETIC", int(round(best_ask_syn)), exec_volume)
                comp_orders = self.convert_synthetic_basket_orders(
                    synthetic_orders=[synthetic_order],
                    order_depths=order_depths,
                    constituents=constituents
                )
                orders_by_product[basket_product] = [basket_order]
                orders_by_product.update(comp_orders)
                return orders_by_product
        return None

    def spread_orders(self, order_depths: Dict[str, OrderDepth],
                      basket_product: str, basket_position: int,
                      spread_data: Dict[str, Any],
                      constituents: Dict[str, int]) -> Dict[str, List[Order]]:
        if basket_product not in order_depths:
            return None
        basket_depth = order_depths[basket_product]
        synthetic_depth = self.get_synthetic_basket_order_depth(constituents, order_depths)
        basket_swmid = self.get_swmid(basket_depth)
        synthetic_swmid = self.get_swmid(synthetic_depth)
        if basket_swmid is None or synthetic_swmid is None:
            return None
        spread = basket_swmid - synthetic_swmid
        spread_data["spread_history"].append(spread)
        window = self.params[basket_product]["spread_std_window"]
        if len(spread_data["spread_history"]) < window:
            return None
        elif len(spread_data["spread_history"]) > window:
            spread_data["spread_history"].pop(0)
        spread_std = np.std(spread_data["spread_history"])
        zscore = (spread - self.params[basket_product]["default_spread_mean"]) / spread_std if spread_std != 0 else 0
        if zscore >= self.params[basket_product]["zscore_threshold"]:
            if basket_position != -self.params[basket_product]["target_position"]:
                return self.execute_spread_orders(
                    -self.params[basket_product]["target_position"],
                    basket_position,
                    order_depths,
                    basket_product,
                    constituents,
                )
        if zscore <= -self.params[basket_product]["zscore_threshold"]:
            if basket_position != self.params[basket_product]["target_position"]:
                return self.execute_spread_orders(
                    self.params[basket_product]["target_position"],
                    basket_position,
                    order_depths,
                    basket_product,
                    constituents,
                )
        spread_data["prev_zscore"] = zscore
        return None

    # ---------------
    # Methods from file 2 (order management, Black-Scholes based hedging, and generic orders)
    # ---------------
    def iceberg(self, product: str, quantity: int) -> int:
        prod_params = self.params.get(product, {})
        if "iceberg_peak" in prod_params:
            peak = prod_params["iceberg_peak"]
            return int(math.copysign(min(abs(quantity), peak), quantity))
        else:
            return quantity

    def take_best_orders(
        self,
        product: str,
        fair_value: float,
        take_width: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
    ) -> (int, int):
        position_limit = self.LIMIT[product]
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if (not prevent_adverse or best_ask_amount <= adverse_volume) and best_ask <= fair_value - take_width:
                quantity = min(best_ask_amount, position_limit - position)
                if quantity > 0:
                    visible_qty = self.iceberg(product, quantity)
                    orders.append(Order(product, best_ask, visible_qty))
                    buy_order_volume += quantity
                    order_depth.sell_orders[best_ask] += quantity
                    if order_depth.sell_orders[best_ask] == 0:
                        del order_depth.sell_orders[best_ask]
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            best_bid_amount = order_depth.buy_orders[best_bid]
            if (not prevent_adverse or best_bid_amount <= adverse_volume) and best_bid >= fair_value + take_width:
                quantity = min(best_bid_amount, position_limit + position)
                if quantity > 0:
                    visible_qty = self.iceberg(product, quantity)
                    orders.append(Order(product, best_bid, -visible_qty))
                    sell_order_volume += quantity
                    order_depth.buy_orders[best_bid] -= quantity
                    if order_depth.buy_orders[best_bid] == 0:
                        del order_depth.buy_orders[best_bid]
        return buy_order_volume, sell_order_volume

    def market_make(
        self,
        product: str,
        orders: List[Order],
        bid: float,
        ask: float,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> (int, int):
        buy_qty = self.LIMIT[product] - (position + buy_order_volume)
        if buy_qty > 0:
            visible_qty = self.iceberg(product, buy_qty)
            orders.append(Order(product, bid, visible_qty))
        sell_qty = self.LIMIT[product] + (position - sell_order_volume)
        if sell_qty > 0:
            visible_qty = self.iceberg(product, sell_qty)
            orders.append(Order(product, ask, -visible_qty))
        return buy_order_volume, sell_order_volume

    def clear_position_order(
        self,
        product: str,
        fair_value: float,
        width: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_order_volume: int,
        sell_order_volume: int,
    ) -> (int, int):
        pos_after_take = position + buy_order_volume - sell_order_volume
        fair_bid = round(fair_value - width)
        fair_ask = round(fair_value + width)
        buy_cap = self.LIMIT[product] - (position + buy_order_volume)
        sell_cap = self.LIMIT[product] + (position - sell_order_volume)
        if pos_after_take > 0:
            qty = sum(v for p, v in order_depth.buy_orders.items() if p >= fair_ask)
            qty = min(qty, pos_after_take, sell_cap)
            if qty > 0:
                visible_qty = self.iceberg(product, qty)
                orders.append(Order(product, fair_ask, -visible_qty))
                sell_order_volume += qty
        elif pos_after_take < 0:
            qty = sum(abs(v) for p, v in order_depth.sell_orders.items() if p <= fair_bid)
            qty = min(qty, -pos_after_take, buy_cap)
            if qty > 0:
                visible_qty = self.iceberg(product, qty)
                orders.append(Order(product, fair_bid, visible_qty))
                buy_order_volume += qty
        return buy_order_volume, sell_order_volume

    def take_orders(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_value: float,
        take_width: float,
        position: int,
        prevent_adverse: bool = False,
        adverse_volume: int = 0,
    ) -> (List[Order], int, int):
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
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_order_volume, sell_order_volume = self.clear_position_order(
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
    ) -> (List[Order], int, int):
        orders: List[Order] = []
        asks_above = [p for p in order_depth.sell_orders if p > fair_value + disregard_edge]
        bids_below = [p for p in order_depth.buy_orders if p < fair_value - disregard_edge]
        best_ask = min(asks_above) if asks_above else None
        best_bid = max(bids_below) if bids_below else None
        ask = round(fair_value + default_edge)
        if best_ask is not None:
            ask = best_ask if abs(best_ask - fair_value) <= join_edge else best_ask - 1
        bid = round(fair_value - default_edge)
        if best_bid is not None:
            bid = best_bid if abs(fair_value - best_bid) <= join_edge else best_bid + 1
        if manage_position:
            if position > soft_position_limit:
                ask -= 1
            elif position < -soft_position_limit:
                bid += 1
        buy_order_volume, sell_order_volume = self.market_make(product, orders, bid, ask, position, buy_order_volume, sell_order_volume)
        return orders, buy_order_volume, sell_order_volume

    def kelp_fair_value(self, order_depth: OrderDepth, trader_obj: dict) -> float or None:
        if not (order_depth.sell_orders and order_depth.buy_orders):
            return None
        best_ask = min(order_depth.sell_orders)
        best_bid = max(order_depth.buy_orders)
        filt_ask = [p for p, v in order_depth.sell_orders.items() if -v >= self.params[Product.KELP]["adverse_volume"]]
        filt_bid = [p for p, v in order_depth.buy_orders.items() if v >= self.params[Product.KELP]["adverse_volume"]]
        mm_ask = min(filt_ask) if filt_ask else None
        mm_bid = max(filt_bid) if filt_bid else None
        if mm_ask is None or mm_bid is None:
            mid = trader_obj.get("kelp_last_price", (best_ask + best_bid) / 2)
        else:
            mid = (mm_ask + mm_bid) / 2
        if "kelp_last_price" in trader_obj:
            last = trader_obj["kelp_last_price"]
            ret = (mid - last) / last
            pred = ret * self.params[Product.KELP]["reversion_beta"]
            fair = mid * (1 + pred)
        else:
            fair = mid
        trader_obj["kelp_last_price"] = mid
        return fair

    def squid_ink_fair_value(self, order_depth: OrderDepth, trader_obj: dict) -> float or None:
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            filtered_ask = [price for price in order_depth.sell_orders if abs(order_depth.sell_orders[price]) >= self.params[Product.SQUID_INK]["adverse_volume"]]
            filtered_bid = [price for price in order_depth.buy_orders if abs(order_depth.buy_orders[price]) >= self.params[Product.SQUID_INK]["adverse_volume"]]
            mm_ask = min(filtered_ask) if filtered_ask else None
            mm_bid = max(filtered_bid) if filtered_bid else None
            if mm_ask is None or mm_bid is None:
                mid = trader_obj.get("squid_ink_last_price", (best_ask + best_bid) / 2)
            else:
                mid = (mm_ask + mm_bid) / 2
            if "squid_ink_last_price" in trader_obj:
                last = trader_obj["squid_ink_last_price"]
                ret = (mid - last) / last
                pred = ret * self.params[Product.SQUID_INK]["reversion_beta"]
                fair = mid * (1 + pred)
            else:
                fair = mid
            trader_obj["squid_ink_last_price"] = mid
            return fair
        return None

    # Additional methods from file 2 for volcanic rock hedging and voucher pricing
    def _calc_time_to_expiry(self, product: str, current_round: int) -> float:
        expiration = 7  # rounds to expiration
        remaining_rounds = max(expiration - (current_round - 1), 0)
        return remaining_rounds / 250

    def stop_loss_orders(self, product: str, order_depth: OrderDepth, position: int, current_mid: float, traderData: dict) -> List[Order]:
        orders = []
        if product not in traderData or "entry_price" not in traderData[product]:
            traderData.setdefault(product, {})["entry_price"] = current_mid
            return orders
        entry_price = traderData[product]["entry_price"]
        if position > 0 and current_mid < entry_price * 0.95:
            if order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders)
                orders.append(Order(product, best_bid, -position))
        elif position < 0 and current_mid > entry_price * 1.05:
            if order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders)
                orders.append(Order(product, best_ask, -position))
        return orders

    def mean_reversion_orders(self, product: str, order_depth: OrderDepth, position: int, current_mid: float, traderData: dict) -> List[Order]:
        orders = []
        traderData.setdefault(product, {}).setdefault("price_history", [])
        price_history = traderData[product]["price_history"]
        price_history.append(current_mid)
        if len(price_history) > 15:
            price_history.pop(0)
        if len(price_history) < 15:
            return orders
        moving_avg_price = np.mean(price_history)
        deviation = (current_mid - moving_avg_price) / moving_avg_price
        if deviation > 0.02:
            if position > 0:
                if order_depth.buy_orders:
                    best_bid = max(order_depth.buy_orders)
                    orders.append(Order(product, best_bid, -position))
            elif position == 0:
                if order_depth.buy_orders:
                    best_bid = max(order_depth.buy_orders)
                    orders.append(Order(product, best_bid, -min(10, self.LIMIT[product])))
        elif deviation < -0.02:
            if position < 0:
                if order_depth.sell_orders:
                    best_ask = min(order_depth.sell_orders)
                    orders.append(Order(product, best_ask, -position))
            elif position == 0:
                if order_depth.sell_orders:
                    best_ask = min(order_depth.sell_orders)
                    orders.append(Order(product, best_ask, min(10, self.LIMIT[product])))
        return orders

    def get_voucher_mid_price(self, voucher_order_depth: OrderDepth, voucherData: dict) -> float:
        if voucher_order_depth.buy_orders and voucher_order_depth.sell_orders:
            best_bid = max(voucher_order_depth.buy_orders)
            best_ask = min(voucher_order_depth.sell_orders)
            voucherData["prev_voucher_price"] = (best_bid + best_ask) / 2
            return (best_bid + best_ask) / 2
        else:
            return voucherData.get("prev_voucher_price", 0)

    def voucher_orders(self, voucher_order_depth: OrderDepth, voucher_position: int, 
                       traderData: dict, volatility: float, product: str) -> (List[Order], List[Order]):
        traderData.setdefault("past_voucher_vol", []).append(volatility)
        window = self.params[product]["std_window"]
        if len(traderData["past_voucher_vol"]) > window:
            traderData["past_voucher_vol"].pop(0)
        if len(traderData["past_voucher_vol"]) < window:
            return None, None
        moving_avg = np.mean(traderData["past_voucher_vol"])
        moving_std = np.std(traderData["past_voucher_vol"])
        vol_z_score = (volatility - moving_avg) / (moving_std if moving_std != 0 else 1)
        
        if vol_z_score >= self.params[product]["zscore_threshold"]:
            if voucher_position != -self.LIMIT[product]:
                target_voucher_position = -self.LIMIT[product]
                if voucher_order_depth.buy_orders:
                    best_bid = max(voucher_order_depth.buy_orders)
                    target_quantity = abs(target_voucher_position - voucher_position)
                    quantity = min(target_quantity, abs(voucher_order_depth.buy_orders[best_bid]))
                    quote_quantity = target_quantity - quantity
                    if quote_quantity == 0:
                        return [Order(product, best_bid, -quantity)], []
                    else:
                        return ([Order(product, best_bid, -quantity)],
                                [Order(product, best_bid, -quote_quantity)])
        elif vol_z_score <= -self.params[product]["zscore_threshold"]:
            if voucher_position != self.LIMIT[product]:
                target_voucher_position = self.LIMIT[product]
                if voucher_order_depth.sell_orders:
                    best_ask = min(voucher_order_depth.sell_orders)
                    target_quantity = abs(target_voucher_position - voucher_position)
                    quantity = min(target_quantity, abs(voucher_order_depth.sell_orders[best_ask]))
                    quote_quantity = target_quantity - quantity
                    if quote_quantity == 0:
                        return [Order(product, best_ask, quantity)], []
                    else:
                        return ([Order(product, best_ask, quantity)],
                                [Order(product, best_ask, quote_quantity)])
        return None, None

    def volcanic_rock_hedge_orders(self,
                                   rock_order_depth: OrderDepth,
                                   voucher_order_depth: OrderDepth,
                                   voucher_orders: list,
                                   rock_position: int,
                                   voucher_position: int,
                                   delta: float) -> List[Order]:
        if voucher_orders is None or len(voucher_orders) == 0:
            voucher_position_after_trade = voucher_position
        else:
            voucher_position_after_trade = voucher_position + sum(order.quantity for order in voucher_orders)
        target_rock_position = -delta * voucher_position_after_trade
        if target_rock_position == rock_position:
            return []
        target_rock_quantity = target_rock_position - rock_position
        orders = []
        if target_rock_quantity > 0:
            best_ask = min(rock_order_depth.sell_orders)
            quantity = min(abs(target_rock_quantity), self.LIMIT[Product.VOLCANIC_ROCK] - rock_position)
            if quantity > 0:
                orders.append(Order(Product.VOLCANIC_ROCK, best_ask, round(quantity)))
        elif target_rock_quantity < 0:
            best_bid = max(rock_order_depth.buy_orders)
            quantity = min(abs(target_rock_quantity), self.LIMIT[Product.VOLCANIC_ROCK] + rock_position)
            if quantity > 0:
                orders.append(Order(Product.VOLCANIC_ROCK, best_bid, -round(quantity)))
        return orders
    
    def macaron_fair_value(self,
                           sugar_price: float,
                           transport_fees: float,
                           import_tariff: float,
                           export_tariff: float,
                           sunlight_index: float) -> float:
        p = self.params[Product.MAGNIFICENT_MACARONS]
        # base cost from sugar
        fair = sugar_price * p["fair_value_multiplier"]
        # add buy‑side fees
        fair += transport_fees + import_tariff
        # panic premium if below CSI
        if sunlight_index < p["CSI"]:
            fair *= 1.10
        return fair


    # ------------------------------------------------------------
    # The merged run() method: processes orders for all products.
    # ------------------------------------------------------------
    def run(self, state: TradingState) -> (Dict[str, List[Order]], int, str):
        traderData = jsonpickle.decode(state.traderData) if state.traderData else {}
        results: Dict[str, List[Order]] = {}
        buy_vol = sell_vol = 0
        ROCK_FLOW_THRESHOLD = 200
        ROCK_LIMIT_BOOST   = 1.5
        ROCK_WIDTH_FACTOR  = 0.5
        # RAINFOREST_RESIN logic with moving average update and stop loss:
        if Product.RAINFOREST_RESIN in state.order_depths:
            od = state.order_depths[Product.RAINFOREST_RESIN]
            pos = state.position.get(Product.RAINFOREST_RESIN, 0)
            self.update_price_history(Product.RAINFOREST_RESIN, od)
            fv = self.get_moving_average(Product.RAINFOREST_RESIN)
            stop_orders = self.apply_stop_loss(Product.RAINFOREST_RESIN, od, fv, pos)
            if stop_orders:
                results[Product.RAINFOREST_RESIN] = stop_orders
            else:
                orders_take, buy_vol, sell_vol = self.take_orders(
                    Product.RAINFOREST_RESIN, od, fv,
                    self.params[Product.RAINFOREST_RESIN]["take_width"], pos
                )
                orders_clear, buy_vol, sell_vol = self.clear_orders(
                    Product.RAINFOREST_RESIN, od, fv,
                    self.params[Product.RAINFOREST_RESIN]["clear_width"], pos, buy_vol, sell_vol
                )
                orders_make, _, _ = self.make_orders(
                    Product.RAINFOREST_RESIN, od, fv, pos, buy_vol, sell_vol,
                    self.params[Product.RAINFOREST_RESIN]["disregard_edge"],
                    self.params[Product.RAINFOREST_RESIN]["join_edge"],
                    self.params[Product.RAINFOREST_RESIN]["default_edge"],
                    True, self.params[Product.RAINFOREST_RESIN]["soft_position_limit"]
                )
                results[Product.RAINFOREST_RESIN] = orders_take + orders_clear + orders_make

        # KELP logic:
        if Product.KELP in state.order_depths:
            od = state.order_depths[Product.KELP]
            pos = state.position.get(Product.KELP, 0)
            fair = self.kelp_fair_value(od, traderData)
            if fair is not None:
                stop_orders = self.apply_stop_loss(Product.KELP, od, fair, pos)
                if stop_orders:
                    results[Product.KELP] = stop_orders
                else:
                    orders_take, buy_vol, sell_vol = self.take_orders(
                        Product.KELP, od, fair, self.params[Product.KELP]["take_width"], pos,
                        self.params[Product.KELP]["prevent_adverse"], self.params[Product.KELP]["adverse_volume"]
                    )
                    orders_clear, buy_vol, sell_vol = self.clear_orders(
                        Product.KELP, od, fair, self.params[Product.KELP]["clear_width"], pos, buy_vol, sell_vol
                    )
                    orders_make, _, _ = self.make_orders(
                        Product.KELP, od, fair, pos, buy_vol, sell_vol,
                        self.params[Product.KELP]["disregard_edge"],
                        self.params[Product.KELP]["join_edge"],
                        self.params[Product.KELP]["default_edge"]
                    )
                    results[Product.KELP] = orders_take + orders_clear + orders_make

        # Basket spread orders for PICNIC_BASKET products:
        for basket_product in [Product.PICNIC_BASKET1, Product.PICNIC_BASKET2]:
            if basket_product not in state.order_depths:
                continue
            basket_position = state.position.get(basket_product, 0)
            constituents = self.params[basket_product]["basket_constituents"]
            spread_data = traderData.get(basket_product, {"spread_history": [], "prev_zscore": 0})
            orders = self.spread_orders(state.order_depths, basket_product, basket_position, spread_data, constituents)
            if orders is not None:
                for prod, prod_orders in orders.items():
                    results.setdefault(prod, []).extend(prod_orders)
            traderData[basket_product] = spread_data

        # SQUID_INK logic:
        if Product.SQUID_INK in state.order_depths:
            od = state.order_depths[Product.SQUID_INK]
            pos = state.position.get(Product.SQUID_INK, 0)
            fair = self.squid_ink_fair_value(od, traderData)
            if fair is not None:
                orders, buy_vol, sell_vol = self.take_orders(
                    Product.SQUID_INK, od, fair, self.params[Product.SQUID_INK]["take_width"], pos,
                    self.params[Product.SQUID_INK]["prevent_adverse"], self.params[Product.SQUID_INK]["adverse_volume"]
                )
                clr, buy_vol, sell_vol = self.clear_orders(
                    Product.SQUID_INK, od, fair, self.params[Product.SQUID_INK]["clear_width"], pos, buy_vol, sell_vol
                )
                mk, _, _ = self.make_orders(
                    Product.SQUID_INK, od, fair, pos, buy_vol, sell_vol,
                    self.params[Product.SQUID_INK]["disregard_edge"],
                    self.params[Product.SQUID_INK]["join_edge"],
                    self.params[Product.SQUID_INK]["default_edge"]
                )
                results[Product.SQUID_INK] = orders + clr + mk

        # VOLCANIC_ROCK and voucher-based hedging:
        rock_flow_by_cp: Dict[Any, int] = {}
        for own in state.own_trades:
            if own.symbol == Product.VOLCANIC_ROCK and own.counter_party is not None:
                rock_flow_by_cp[own.counter_party] = (
                    rock_flow_by_cp.get(own.counter_party, 0)
                    + abs(own.quantity)
                )
        candidate_hedge_orders = []
        if Product.VOLCANIC_ROCK in state.order_depths:
            rock_od       = state.order_depths[Product.VOLCANIC_ROCK]
            rock_mid      = (min(rock_od.buy_orders) + max(rock_od.sell_orders)) / 2
            rock_position = state.position.get(Product.VOLCANIC_ROCK, 0)
            current_round = getattr(state, "current_round", 1)

            # pull base widths & limit
            p       = self.params[Product.VOLCANIC_ROCK]
            take_w  = p["take_width"]
            clear_w = p["clear_width"]
            disp_e  = p["disregard_edge"]
            join_e  = p["join_edge"]
            def_e   = p["default_edge"]
            limit   = self.LIMIT[Product.VOLCANIC_ROCK]

            # if any single counter_party exceeds the flow threshold → tighten mode
            if any(flow >= ROCK_FLOW_THRESHOLD for flow in rock_flow_by_cp.values()):
                take_w  *= ROCK_WIDTH_FACTOR
                clear_w *= ROCK_WIDTH_FACTOR
                def_e   *= ROCK_WIDTH_FACTOR
                limit    = int(limit * ROCK_LIMIT_BOOST)

            candidate_hedge_orders: List[Order] = []

            # 2.1) Rock stop‑loss & mean‑reversion
            stop_loss = self.stop_loss_orders(
                Product.VOLCANIC_ROCK, rock_od,
                rock_position, rock_mid, traderData
            )
            mean_rev = self.mean_reversion_orders(
                Product.VOLCANIC_ROCK, rock_od,
                rock_position, rock_mid, traderData
            )
            if stop_loss:
                candidate_hedge_orders.extend(stop_loss)
            if mean_rev:
                candidate_hedge_orders.extend(mean_rev)

            # 2.2) Voucher processing & delta‑hedge
            for voucher in [
                Product.VOLCANIC_ROCK_VOUCHER_9500,
                Product.VOLCANIC_ROCK_VOUCHER_9750,
                Product.VOLCANIC_ROCK_VOUCHER_10000,
                Product.VOLCANIC_ROCK_VOUCHER_10250,
                Product.VOLCANIC_ROCK_VOUCHER_10500
            ]:
                if voucher in state.order_depths:
                    voucher_od       = state.order_depths[voucher]
                    voucher_position = state.position.get(voucher, 0)
                    traderData.setdefault(
                        voucher,
                        {"prev_voucher_price": 0, "past_voucher_vol": []}
                    )

                    # mid price & entry tracking
                    voucher_mid = self.get_voucher_mid_price(
                        voucher_od, traderData[voucher]
                    )
                    if "entry_price" not in traderData[voucher]:
                        traderData[voucher]["entry_price"] = voucher_mid

                    # implied vol & delta
                    tte    = self._calc_time_to_expiry(voucher, current_round)
                    strike = self.params[voucher]["strike"]
                    vol    = BlackScholes.implied_volatility(
                        voucher_mid, rock_mid, strike, tte
                    )
                    delta  = BlackScholes.delta(rock_mid, strike, tte, vol)

                    # generate voucher orders and rock hedge orders
                    voucher_take, voucher_make = self.voucher_orders(
                        voucher_od, voucher_position,
                        traderData[voucher], vol, voucher
                    )
                    rock_hedge = self.volcanic_rock_hedge_orders(
                        rock_od, voucher_od,
                        voucher_take, rock_position,
                        voucher_position, delta
                    )

                    # record voucher trades
                    if voucher_take or voucher_make:
                        results[voucher] = (voucher_take or []) + (voucher_make or [])
                    # accumulate any rock hedge orders
                    if rock_hedge:
                        candidate_hedge_orders.extend(rock_hedge)

            # 2.3) Emit any accumulated rock hedges
            if candidate_hedge_orders:
                results.setdefault(Product.VOLCANIC_ROCK, []).extend(candidate_hedge_orders)
     
                
        # -------------------------
        # MAGNIFICENT_MACARONS logic
        # -------------------------
        if Product.MAGNIFICENT_MACARONS in state.order_depths and \
        Product.MAGNIFICENT_MACARONS in state.observations.conversionObservations:

            od = state.order_depths[Product.MAGNIFICENT_MACARONS]
            pos = state.position.get(Product.MAGNIFICENT_MACARONS, 0)
            obs = state.observations
            p = self.params[Product.MAGNIFICENT_MACARONS]

            co = obs.conversionObservations[Product.MAGNIFICENT_MACARONS]

            fv = self.macaron_fair_value(
                co.sugarPrice,
                co.transportFees,
                co.importTariff,
                co.exportTariff,
                co.sunlightIndex
            )
            fv -= pos * p["storage_cost"]

            orders_take, buy_v, sell_v = self.take_orders(Product.MAGNIFICENT_MACARONS, od, fv, p["take_width"], pos)
            orders_clear, buy_v, sell_v = self.clear_orders(Product.MAGNIFICENT_MACARONS, od, fv, p["clear_width"], pos, buy_v, sell_v)
            orders_make, _, _ = self.make_orders(
                Product.MAGNIFICENT_MACARONS, od, fv, pos, buy_v, sell_v,
                p["disregard_edge"], p["join_edge"], p["default_edge"]
            )

            results[Product.MAGNIFICENT_MACARONS] = orders_take + orders_clear + orders_make

            buy_cost = co.askPrice + co.transportFees + co.importTariff
            sell_value = co.bidPrice - (co.transportFees + co.exportTariff)
            conv_qty = 0
            if fv > buy_cost and pos < self.LIMIT[Product.MAGNIFICENT_MACARONS]:
                conv_qty = min(p["conversion_limit"], self.LIMIT[Product.MAGNIFICENT_MACARONS] - pos)
            elif fv < sell_value and pos > 0:
                conv_qty = -min(p["conversion_limit"], pos)
            conversions = abs(conv_qty)
        else:
            conversions = 0


        # encode and return
        traderData_encoded = jsonpickle.encode(traderData)
        return results, conversions, traderData_encoded