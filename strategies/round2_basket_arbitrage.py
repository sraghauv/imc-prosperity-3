from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Any
import jsonpickle
import numpy as np
import math

class Product:
    RAINFOREST_RESIN = "RAINFOREST_RESIN"
    KELP = "KELP"
    PICNIC_BASKET1 = "PICNIC_BASKET1"
    PICNIC_BASKET2 = "PICNIC_BASKET2"
    CROISSANTS = "CROISSANTS"
    JAMS = "JAMS"
    DJEMBES = "DJEMBES"
    SQUID_INK = "SQUID_INK"

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
        "fair_value": 2045,
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
        "fair_value": 1800,
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
}

class Trader:
    def __init__(self, params: Dict = None):
        if params is None:
            params = PARAMS
        self.params = params
        self.LIMIT = {
            Product.RAINFOREST_RESIN: 20,
            Product.KELP: 20,
            Product.PICNIC_BASKET1: 60,
            Product.PICNIC_BASKET2: 100,
            Product.CROISSANTS: 250,
            Product.JAMS: 350,
            Product.DJEMBES: 60,
            Product.SQUID_INK: 4,
        }
        self.spread_history = {
            Product.PICNIC_BASKET1: [],
            Product.PICNIC_BASKET2: [],
        }

        # ✅ Initialize moving average history
        self.price_history = {
            prod: [] for prod, p in self.params.items() if "fair_value" in p
        }


    def get_moving_average(self, product: str, window_size: int = 800) -> float:
        history = self.price_history[product]
        if not history:
            # fall back to whatever you configured
            return self.params[product].get("fair_value", 10000)
        return float(np.mean(history[-window_size:]))

    def update_price_history(self, product: str, order_depth: OrderDepth):
        if order_depth.buy_orders and order_depth.sell_orders:
            best_bid = max(order_depth.buy_orders)
            best_ask = min(order_depth.sell_orders)
            mid_price = (best_bid + best_ask) / 2
            self.price_history[product].append(mid_price)
            if len(self.price_history[product]) > 800:
                self.price_history[product].pop(0)

    def apply_stop_loss(self, product: str, order_depth: OrderDepth, fair_value: float, position: int) -> List[Order]:
        orders = []
        threshold = self.params.get(product, {}).get("stop_loss_threshold", 0)
        if threshold == 0:
            return orders
        if position > 0 and order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            if best_bid < fair_value - threshold:
                orders.append(Order(product, int(best_bid), -position))
        elif position < 0 and order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            if best_ask > fair_value + threshold:
                orders.append(Order(product, int(best_ask), -position))
        return orders

    def take_best_orders(self, product: str, fair_value: float, take_width: float, orders: List[Order],
                         order_depth: OrderDepth, position: int, buy_order_volume: int, sell_order_volume: int,
                         prevent_adverse: bool = False, adverse_volume: int = 0) -> (int, int):
        position_limit = self.LIMIT[product]
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if (not prevent_adverse or best_ask_amount <= adverse_volume) and best_ask <= fair_value - take_width:
                qty = min(best_ask_amount, position_limit - position)
                if qty > 0:
                    orders.append(Order(product, int(round(best_ask)), qty))
                    buy_order_volume += qty
                    order_depth.sell_orders[best_ask] += qty
                    if order_depth.sell_orders[best_ask] == 0:
                        del order_depth.sell_orders[best_ask]
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            if (not prevent_adverse or best_bid_amount <= adverse_volume) and best_bid >= fair_value + take_width:
                qty = min(best_bid_amount, position_limit + position)
                if qty > 0:
                    orders.append(Order(product, int(round(best_bid)), -qty))
                    sell_order_volume += qty
                    order_depth.buy_orders[best_bid] -= qty
                    if order_depth.buy_orders[best_bid] == 0:
                        del order_depth.buy_orders[best_bid]
        return buy_order_volume, sell_order_volume

    def market_make(self, product: str, orders: List[Order], bid: int, ask: int,
                    position: int, buy_order_volume: int, sell_order_volume: int) -> (int, int):
        buy_qty = self.LIMIT[product] - (position + buy_order_volume)
        if buy_qty > 0:
            orders.append(Order(product, int(bid), buy_qty))
        sell_qty = self.LIMIT[product] + (position - sell_order_volume)
        if sell_qty > 0:
            orders.append(Order(product, int(ask), -sell_qty))
        return buy_order_volume, sell_order_volume

    def clear_position_order(self, product: str, fair_value: float, width: int, orders: List[Order],
                             order_depth: OrderDepth, position: int, buy_order_volume: int, sell_order_volume: int) -> (int, int):
        pos_after_take = position + buy_order_volume - sell_order_volume
        fair_bid = int(round(fair_value - width))
        fair_ask = int(round(fair_value + width))
        buy_cap = self.LIMIT[product] - (position + buy_order_volume)
        sell_cap = self.LIMIT[product] + (position - sell_order_volume)
        if pos_after_take > 0:
            qty = sum(v for p, v in order_depth.buy_orders.items() if p >= fair_ask)
            qty = min(qty, pos_after_take, sell_cap)
            if qty > 0:
                orders.append(Order(product, fair_ask, -qty))
                sell_order_volume += qty
        elif pos_after_take < 0:
            qty = sum(abs(v) for p, v in order_depth.sell_orders.items() if p <= fair_bid)
            qty = min(qty, -pos_after_take, buy_cap)
            if qty > 0:
                orders.append(Order(product, fair_bid, qty))
                buy_order_volume += qty
        return buy_order_volume, sell_order_volume

    def take_orders(self, product: str, order_depth: OrderDepth, fair_value: float,
                    take_width: float, position: int, prevent_adverse: bool = False, adverse_volume: int = 0) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_vol, sell_vol = self.take_best_orders(product, fair_value, take_width, orders, order_depth, position, 0, 0, prevent_adverse, adverse_volume)
        return orders, buy_vol, sell_vol

    def clear_orders(self, product: str, order_depth: OrderDepth, fair_value: float, clear_width: int,
                     position: int, buy_vol: int, sell_vol: int) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_vol, sell_vol = self.clear_position_order(product, fair_value, clear_width, orders, order_depth, position, buy_vol, sell_vol)
        return orders, buy_vol, sell_vol

    def make_orders(self, product: str, order_depth: OrderDepth, fair_value: float, position: int,
                    buy_vol: int, sell_vol: int, disregard_edge: float, join_edge: float, default_edge: float,
                    manage_position: bool = False, soft_position_limit: int = 0) -> (List[Order], int, int):
        orders: List[Order] = []
        asks_above = [p for p in order_depth.sell_orders if p > fair_value + disregard_edge]
        bids_below = [p for p in order_depth.buy_orders if p < fair_value - disregard_edge]
        best_ask = min(asks_above) if asks_above else None
        best_bid = max(bids_below) if bids_below else None
        ask = int(round(fair_value + default_edge))
        if best_ask is not None:
            ask = int(best_ask) if abs(best_ask - fair_value) <= join_edge else int(best_ask) - 1
        bid = int(round(fair_value - default_edge))
        if best_bid is not None:
            bid = int(best_bid) if abs(fair_value - best_bid) <= join_edge else int(best_bid) + 1
        if manage_position:
            if position > soft_position_limit:
                ask -= 1
            elif position < -soft_position_limit:
                bid += 1
        buy_vol, sell_vol = self.market_make(product, orders, bid, ask, position, buy_vol, sell_vol)
        return orders, buy_vol, sell_vol

    def kelp_fair_value(self, order_depth: OrderDepth, trader_obj: dict) -> float or None:
        if not (order_depth.sell_orders and order_depth.buy_orders):
            return None
        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())
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

    def get_swmid(self, order_depth: OrderDepth) -> int or None:
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
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
            best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else 0
            best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else float('inf')
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
        component_orders = {asset: [] for asset in constituents.keys()}
        for order in synthetic_orders:
            qty = order.quantity
            if qty > 0:
                for asset, weight in constituents.items():
                    # if asset == Product.CROISSANTS:
                    #     continue
                    if asset in order_depths and order_depths[asset].buy_orders:
                        best_bid = max(order_depths[asset].buy_orders.keys())
                        component_orders[asset].append(Order(asset, int(round(best_bid)), -qty * weight))
            elif qty < 0:
                for asset, weight in constituents.items():
                    # if asset == Product.CROISSANTS:
                    #     continue
                    if asset in order_depths and order_depths[asset].sell_orders:
                        best_ask = min(order_depths[asset].sell_orders.keys())
                        component_orders[asset].append(Order(asset, int(round(best_ask)), -qty * weight))
        return component_orders

    def execute_spread_orders(self, target_position: int, basket_position: int,
                                order_depths: Dict[str, OrderDepth],
                                basket_product: str, constituents: Dict[str, int]) -> Dict[str, List[Order]]:
        if target_position == basket_position:
            return None
        target_qty = abs(target_position - basket_position)
        basket_depth = order_depths[basket_product]
        synthetic_depth = self.get_synthetic_basket_order_depth(constituents, order_depths)
        orders_by_product = {}
        if target_position > basket_position:
            if basket_depth.sell_orders:
                best_ask = min(basket_depth.sell_orders.keys())
                basket_volume = abs(basket_depth.sell_orders[best_ask])
            else:
                best_ask = None
                basket_volume = 0
            if synthetic_depth.buy_orders:
                best_bid_syn = max(synthetic_depth.buy_orders.keys())
                synthetic_volume = abs(synthetic_depth.buy_orders[best_bid_syn])
            else:
                best_bid_syn = None
                synthetic_volume = 0
            exec_volume = min(basket_volume, synthetic_volume, target_qty)
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
            if basket_depth.buy_orders:
                best_bid = max(basket_depth.buy_orders.keys())
                basket_volume = abs(basket_depth.buy_orders[best_bid])
            else:
                best_bid = None
                basket_volume = 0
            if synthetic_depth.sell_orders:
                best_ask_syn = min(synthetic_depth.sell_orders.keys())
                synthetic_volume = abs(synthetic_depth.sell_orders[best_ask_syn])
            else:
                best_ask_syn = None
                synthetic_volume = 0
            exec_volume = min(basket_volume, synthetic_volume, target_qty)
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

    def iceberg(self, product: str, quantity: int) -> int:
        peak = self.params[product].get("iceberg_peak", abs(quantity))
        return int(math.copysign(min(abs(quantity), peak), quantity))

    def squid_ink_take_best_orders(self, product: str, fair_value: int, take_width: float,
                                   orders: List[Order], order_depth: OrderDepth, position: int,
                                   buy_order_volume: int, sell_order_volume: int,
                                   prevent_adverse: bool = False, adverse_volume: int = 0) -> (int, int):
        position_limit = self.LIMIT[product]
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_ask_amount = -order_depth.sell_orders[best_ask]
            if not prevent_adverse or abs(best_ask_amount) <= adverse_volume:
                if best_ask <= fair_value - take_width:
                    quantity = min(best_ask_amount, position_limit - position)
                    if quantity > 0:
                        orders.append(Order(product, best_ask, self.iceberg(product, quantity)))
                        buy_order_volume += quantity
                        order_depth.sell_orders[best_ask] += quantity
                        if order_depth.sell_orders[best_ask] == 0:
                            del order_depth.sell_orders[best_ask]
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_bid_amount = order_depth.buy_orders[best_bid]
            if not prevent_adverse or abs(best_bid_amount) <= adverse_volume:
                if best_bid >= fair_value + take_width:
                    quantity = min(best_bid_amount, position_limit + position)
                    if quantity > 0:
                        orders.append(Order(product, best_bid, -self.iceberg(product, quantity)))
                        sell_order_volume += quantity
                        order_depth.buy_orders[best_bid] -= quantity
                        if order_depth.buy_orders[best_bid] == 0:
                            del order_depth.buy_orders[best_bid]
        return buy_order_volume, sell_order_volume

    def squid_ink_market_make(self, product: str, orders: List[Order], bid: int, ask: int,
                              position: int, buy_order_volume: int, sell_order_volume: int) -> (int, int):
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        if buy_quantity > 0:
            orders.append(Order(product, round(bid), self.iceberg(product, buy_quantity)))
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)
        if sell_quantity > 0:
            orders.append(Order(product, round(ask), -self.iceberg(product, sell_quantity)))
        return buy_order_volume, sell_order_volume

    def squid_ink_clear_position_order(self, product: str, fair_value: float, width: int,
                                       orders: List[Order], order_depth: OrderDepth, position: int,
                                       buy_order_volume: int, sell_order_volume: int) -> (int, int):
        position_after_take = position + buy_order_volume - sell_order_volume
        fair_for_bid = round(fair_value - width)
        fair_for_ask = round(fair_value + width)
        buy_quantity = self.LIMIT[product] - (position + buy_order_volume)
        sell_quantity = self.LIMIT[product] + (position - sell_order_volume)
        if position_after_take > 0:
            clear_quantity = sum(volume for price, volume in order_depth.buy_orders.items() if price >= fair_for_ask)
            clear_quantity = min(clear_quantity, position_after_take)
            sent_quantity = min(sell_quantity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(product, fair_for_ask, -self.iceberg(product, sent_quantity)))
                sell_order_volume += abs(sent_quantity)
        if position_after_take < 0:
            clear_quantity = sum(abs(volume) for price, volume in order_depth.sell_orders.items() if price <= fair_for_bid)
            clear_quantity = min(clear_quantity, abs(position_after_take))
            sent_quantity = min(buy_quantity, clear_quantity)
            if sent_quantity > 0:
                orders.append(Order(product, fair_for_bid, self.iceberg(product, sent_quantity)))
                buy_order_volume += abs(sent_quantity)
        return buy_order_volume, sell_order_volume

    def squid_ink_take_orders(self, product: str, order_depth: OrderDepth, fair_value: float,
                              take_width: float, position: int, prevent_adverse: bool = False,
                              adverse_volume: int = 0) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_order_volume, sell_order_volume = self.squid_ink_take_best_orders(
            product, fair_value, take_width, orders, order_depth, position, 0, 0, prevent_adverse, adverse_volume
        )
        return orders, buy_order_volume, sell_order_volume

    def squid_ink_clear_orders(self, product: str, order_depth: OrderDepth, fair_value: float, clear_width: int,
                               position: int, buy_order_volume: int, sell_order_volume: int) -> (List[Order], int, int):
        orders: List[Order] = []
        buy_order_volume, sell_order_volume = self.squid_ink_clear_position_order(
            product, fair_value, clear_width, orders, order_depth, position, buy_order_volume, sell_order_volume
        )
        return orders, buy_order_volume, sell_order_volume

    def squid_ink_make_orders(self, product: str, order_depth: OrderDepth, fair_value: float, position: int,
                              buy_order_volume: int, sell_order_volume: int, disregard_edge: float,
                              join_edge: float, default_edge: float) -> (List[Order], int, int):
        orders: List[Order] = []
        asks_above_fair = [price for price in order_depth.sell_orders.keys() if price > fair_value + disregard_edge]
        bids_below_fair = [price for price in order_depth.buy_orders.keys() if price < fair_value - disregard_edge]
        best_ask_above_fair = min(asks_above_fair) if len(asks_above_fair) > 0 else None
        best_bid_below_fair = max(bids_below_fair) if len(bids_below_fair) > 0 else None
        ask = round(fair_value + default_edge)
        if best_ask_above_fair is not None:
            if abs(best_ask_above_fair - fair_value) <= join_edge:
                ask = best_ask_above_fair
            else:
                ask = best_ask_above_fair - 1
        bid = round(fair_value - default_edge)
        if best_bid_below_fair is not None:
            if abs(fair_value - best_bid_below_fair) <= join_edge:
                bid = best_bid_below_fair
            else:
                bid = best_bid_below_fair + 1
        buy_order_volume, sell_order_volume = self.squid_ink_market_make(
            product, orders, bid, ask, position, buy_order_volume, sell_order_volume
        )
        return orders, buy_order_volume, sell_order_volume

    def squid_ink_fair_value(self, order_depth: OrderDepth, traderObject) -> float:
        if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            filtered_ask = [price for price in order_depth.sell_orders.keys() if abs(order_depth.sell_orders[price]) >= self.params[Product.SQUID_INK]["adverse_volume"]]
            filtered_bid = [price for price in order_depth.buy_orders.keys() if abs(order_depth.buy_orders[price]) >= self.params[Product.SQUID_INK]["adverse_volume"]]
            mm_ask = min(filtered_ask) if len(filtered_ask) > 0 else None
            mm_bid = max(filtered_bid) if len(filtered_bid) > 0 else None
            if mm_ask is None or mm_bid is None:
                if traderObject.get("squid_ink_last_price", None) is None:
                    mmmid_price = (best_ask + best_bid) / 2
                else:
                    mmmid_price = traderObject["squid_ink_last_price"]
            else:
                mmmid_price = (mm_ask + mm_bid) / 2
            if traderObject.get("squid_ink_last_price", None) is not None:
                last_price = traderObject["squid_ink_last_price"]
                last_returns = (mmmid_price - last_price) / last_price
                pred_returns = last_returns * self.params[Product.SQUID_INK]["reversion_beta"]
                fair = mmmid_price + (mmmid_price * pred_returns)
            else:
                fair = mmmid_price
            traderObject["squid_ink_last_price"] = mmmid_price
            return fair
        return None

    def run(self, state: TradingState) -> (Dict[str, List[Order]], int, str):
        traderObject = {}
        if state.traderData:
            traderObject = jsonpickle.decode(state.traderData)
        result = {}

        # RAINFOREST_RESIN Trading Logic with Moving Average
        if Product.RAINFOREST_RESIN in state.order_depths:
            od = state.order_depths[Product.RAINFOREST_RESIN]
            pos = state.position.get(Product.RAINFOREST_RESIN, 0)

            # Update price history
            self.update_price_history(Product.RAINFOREST_RESIN, od)

            # Use moving average for fair value
            fv = self.get_moving_average(Product.RAINFOREST_RESIN)

            stop_orders = self.apply_stop_loss(Product.RAINFOREST_RESIN, od, fv, pos)
            if stop_orders:
                result[Product.RAINFOREST_RESIN] = stop_orders
            else:
                orders_take, buy_vol, sell_vol = self.take_orders(
                    Product.RAINFOREST_RESIN, od, fv,
                    self.params[Product.RAINFOREST_RESIN]["take_width"], pos)
                orders_clear, buy_vol, sell_vol = self.clear_orders(
                    Product.RAINFOREST_RESIN, od, fv,
                    self.params[Product.RAINFOREST_RESIN]["clear_width"], pos, buy_vol, sell_vol)
                orders_make, _, _ = self.make_orders(
                    Product.RAINFOREST_RESIN, od, fv, pos, buy_vol, sell_vol,
                    self.params[Product.RAINFOREST_RESIN]["disregard_edge"],
                    self.params[Product.RAINFOREST_RESIN]["join_edge"],
                    self.params[Product.RAINFOREST_RESIN]["default_edge"], True,
                    self.params[Product.RAINFOREST_RESIN]["soft_position_limit"])
                result[Product.RAINFOREST_RESIN] = orders_take + orders_clear + orders_make
        if Product.KELP in state.order_depths:
            od = state.order_depths[Product.KELP]
            pos = state.position.get(Product.KELP, 0)
            fair = self.kelp_fair_value(od, traderObject)
            if fair is not None:
                stop_orders = self.apply_stop_loss(Product.KELP, od, fair, pos)
                if stop_orders:
                    result[Product.KELP] = stop_orders
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
                    result[Product.KELP] = orders_take + orders_clear + orders_make
        for basket_product in [Product.PICNIC_BASKET1, Product.PICNIC_BASKET2]:
            if basket_product not in state.order_depths:
                continue
            basket_position = state.position.get(basket_product, 0)
            constituents = self.params[basket_product]["basket_constituents"]
            spread_data = traderObject.get(basket_product, {"spread_history": [], "prev_zscore": 0})
            orders = self.spread_orders(
                state.order_depths, basket_product, basket_position, spread_data, constituents
            )
            if orders is not None:
                for prod, prod_orders in orders.items():
                    if prod in result:
                        result[prod] += prod_orders
                    else:
                        result[prod] = prod_orders
            traderObject[basket_product] = spread_data
        if Product.SQUID_INK in state.order_depths:
            squid_ink_position = state.position.get(Product.SQUID_INK, 0)
            squid_ink_fv = self.squid_ink_fair_value(state.order_depths[Product.SQUID_INK], traderObject)
            squid_ink_take_orders, buy_vol, sell_vol = self.squid_ink_take_orders(
                Product.SQUID_INK, state.order_depths[Product.SQUID_INK], squid_ink_fv,
                self.params[Product.SQUID_INK]["take_width"], squid_ink_position,
                self.params[Product.SQUID_INK]["prevent_adverse"], self.params[Product.SQUID_INK]["adverse_volume"]
            )
            squid_ink_clear_orders, buy_vol, sell_vol = self.squid_ink_clear_orders(
                Product.SQUID_INK, state.order_depths[Product.SQUID_INK], squid_ink_fv,
                self.params[Product.SQUID_INK]["clear_width"], squid_ink_position, buy_vol, sell_vol
            )
            squid_ink_make_orders, _, _ = self.squid_ink_make_orders(
                Product.SQUID_INK, state.order_depths[Product.SQUID_INK], squid_ink_fv,
                squid_ink_position, buy_vol, sell_vol,
                self.params[Product.SQUID_INK]["disregard_edge"],
                self.params[Product.SQUID_INK]["join_edge"],
                self.params[Product.SQUID_INK]["default_edge"]
            )
            result[Product.SQUID_INK] = squid_ink_take_orders + squid_ink_clear_orders + squid_ink_make_orders
        conversions = 1
        traderData = jsonpickle.encode(traderObject)
        return result, conversions, traderData
