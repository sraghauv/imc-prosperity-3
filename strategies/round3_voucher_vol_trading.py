from datamodel import OrderDepth, TradingState, Order  # adjust as needed 
import jsonpickle
import numpy as np
import math
from math import log, sqrt
from statistics import NormalDist

class Product:
    VOLCANIC_ROCK = "VOLCANIC_ROCK"
    VOLCANIC_ROCK_VOUCHER_9500 = "VOLCANIC_ROCK_VOUCHER_9500"
    VOLCANIC_ROCK_VOUCHER_9750 = "VOLCANIC_ROCK_VOUCHER_9750"  # New product
    VOLCANIC_ROCK_VOUCHER_10000 = "VOLCANIC_ROCK_VOUCHER_10000"
    VOLCANIC_ROCK_VOUCHER_10250 = "VOLCANIC_ROCK_VOUCHER_10250"
    VOLCANIC_ROCK_VOUCHER_10500 = "VOLCANIC_ROCK_VOUCHER_10500"

# Parameters now only for the voucher products.
PARAMS = {
    Product.VOLCANIC_ROCK_VOUCHER_9500: {
        "mean_volatility": 0.14,
        "strike": 9500,
        "std_window": 30,
        "zscore_threshold": 1.1
    },
    Product.VOLCANIC_ROCK_VOUCHER_9750: {  # New parameters for the voucher with 9750 strike.
        "mean_volatility": 0.15,
        "strike": 9750,
        "std_window": 30,
        "zscore_threshold": 0.6
    },
    Product.VOLCANIC_ROCK_VOUCHER_10000: {  # New parameters for the voucher with 9750 strike.
        "mean_volatility": 0.15,
        "strike": 10000,
        "std_window": 30,
        "zscore_threshold": 0.5
    },
    Product.VOLCANIC_ROCK_VOUCHER_10250: {  # New parameters for the voucher with 9750 strike.
        "mean_volatility": 0.15,
        "strike": 10250,
        "std_window": 30,
        "zscore_threshold": 0.8
    },
    Product.VOLCANIC_ROCK_VOUCHER_10500: {  # New parameters for the voucher with 9750 strike.
        "mean_volatility": 0.15,
        "strike": 10500,
        "std_window": 30,
        "zscore_threshold": 2.6
    },
}

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

class Trader:
    def __init__(self, params=None):
        if params is None:
            params = PARAMS
        self.params = params
        # Limits for positions: VOLCANIC_ROCK and its vouchers.
        self.LIMIT = {
            Product.VOLCANIC_ROCK: 100,
            Product.VOLCANIC_ROCK_VOUCHER_9500: 0,
            Product.VOLCANIC_ROCK_VOUCHER_9750: 200,  # New limit for the voucher 9750.
            Product.VOLCANIC_ROCK_VOUCHER_10000: 200,
            Product.VOLCANIC_ROCK_VOUCHER_10250: 0,
            Product.VOLCANIC_ROCK_VOUCHER_10500: 200,
        }

    # --- Price and Volatility Functions ---
    def get_voucher_mid_price(self, voucher_order_depth: OrderDepth, traderData: dict):
        # Returns mid price for a voucher.
        if voucher_order_depth.buy_orders and voucher_order_depth.sell_orders:
            best_bid = max(voucher_order_depth.buy_orders.keys())
            best_ask = min(voucher_order_depth.sell_orders.keys())
            traderData["prev_voucher_price"] = (best_bid + best_ask) / 2
            return (best_bid + best_ask) / 2
        else:
            return traderData.get("prev_voucher_price", 0)
    
    # --- Hedge Orders for VOLCANIC_ROCK based on voucher orders ---
    def volcanic_rock_hedge_orders(self,
                                   rock_order_depth: OrderDepth,
                                   voucher_order_depth: OrderDepth,
                                   voucher_orders: list,
                                   rock_position: int,
                                   voucher_position: int,
                                   delta: float) -> list:
        if voucher_orders is None or len(voucher_orders) == 0:
            voucher_position_after_trade = voucher_position
        else:
            voucher_position_after_trade = voucher_position + sum(order.quantity for order in voucher_orders)
        
        target_rock_position = -delta * voucher_position_after_trade
        if target_rock_position == rock_position:
            return None
        
        target_rock_quantity = target_rock_position - rock_position
        orders = []
        if target_rock_quantity > 0:
            best_ask = min(rock_order_depth.sell_orders.keys())
            quantity = min(abs(target_rock_quantity), self.LIMIT[Product.VOLCANIC_ROCK] - rock_position)
            if quantity > 0:
                orders.append(Order(Product.VOLCANIC_ROCK, best_ask, round(quantity)))
        elif target_rock_quantity < 0:
            best_bid = max(rock_order_depth.buy_orders.keys())
            quantity = min(abs(target_rock_quantity), self.LIMIT[Product.VOLCANIC_ROCK] + rock_position)
            if quantity > 0:
                orders.append(Order(Product.VOLCANIC_ROCK, best_bid, -round(quantity)))
        return orders

    def _calc_time_to_expiry(self, product: str, current_round: int) -> float:
        # Voucher expiry in 7 days.
        expiration = 7
        remaining_rounds = max(expiration - (current_round - 1), 0)
        return remaining_rounds / 250

    # --- Stop Loss Function ---
    def stop_loss_orders(self, product: str, order_depth: OrderDepth, position: int, current_mid: float, traderData: dict) -> list:
        orders = []
        if product not in traderData or "entry_price" not in traderData[product]:
            traderData.setdefault(product, {})["entry_price"] = current_mid
            return orders
        entry_price = traderData[product]["entry_price"]
        if position > 0 and current_mid < entry_price * 0.95:
            if order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                orders.append(Order(product, best_bid, -position))
        elif position < 0 and current_mid > entry_price * 1.05:
            if order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                orders.append(Order(product, best_ask, -position))
        return orders

    # --- Mean Reversion Function ---
    def mean_reversion_orders(self, product: str, order_depth: OrderDepth, position: int, current_mid: float, traderData: dict) -> list:
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
                    best_bid = max(order_depth.buy_orders.keys())
                    orders.append(Order(product, best_bid, -position))
            elif position == 0:
                if order_depth.buy_orders:
                    best_bid = max(order_depth.buy_orders.keys())
                    orders.append(Order(product, best_bid, -min(10, self.LIMIT[product])))
        elif deviation < -0.02:
            if position < 0:
                if order_depth.sell_orders:
                    best_ask = min(order_depth.sell_orders.keys())
                    orders.append(Order(product, best_ask, -position))
            elif position == 0:
                if order_depth.sell_orders:
                    best_ask = min(order_depth.sell_orders.keys())
                    orders.append(Order(product, best_ask, min(10, self.LIMIT[product])))
        return orders

    # --- Voucher Orders for voucher products ---
    def voucher_orders(self, voucher_order_depth: OrderDepth, voucher_position: int, 
                       traderData: dict, volatility: float, product: str) -> (list, list):
        # product is either VOLCANIC_ROCK_VOUCHER_9500 or VOLCANIC_ROCK_VOUCHER_9750.
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
                    best_bid = max(voucher_order_depth.buy_orders.keys())
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
                    best_ask = min(voucher_order_depth.sell_orders.keys())
                    target_quantity = abs(target_voucher_position - voucher_position)
                    quantity = min(target_quantity, abs(voucher_order_depth.sell_orders[best_ask]))
                    quote_quantity = target_quantity - quantity
                    if quote_quantity == 0:
                        return [Order(product, best_ask, quantity)], []
                    else:
                        return ([Order(product, best_ask, quantity)],
                                [Order(product, best_ask, quote_quantity)])
        return None, None

    def run(self, state: TradingState):
        traderData = {}
        if state.traderData is not None and state.traderData != "":
            traderData = jsonpickle.decode(state.traderData)
        
        # Initialize trader data for both voucher products.
        traderData.setdefault(Product.VOLCANIC_ROCK_VOUCHER_9500, {"prev_voucher_price": 0, "past_voucher_vol": []})
        traderData.setdefault(Product.VOLCANIC_ROCK_VOUCHER_9750, {"prev_voucher_price": 0, "past_voucher_vol": []})
        traderData.setdefault(Product.VOLCANIC_ROCK_VOUCHER_10000, {"prev_voucher_price": 0, "past_voucher_vol": []})
        traderData.setdefault(Product.VOLCANIC_ROCK_VOUCHER_10250, {"prev_voucher_price": 0, "past_voucher_vol": []})
        traderData.setdefault(Product.VOLCANIC_ROCK_VOUCHER_10500, {"prev_voucher_price": 0, "past_voucher_vol": []})
        
        result = {}
        candidate_hedge_orders = []  # Collect underlying hedge orders.
        
        if Product.VOLCANIC_ROCK in state.order_depths:
            rock_order_depth = state.order_depths[Product.VOLCANIC_ROCK]
            rock_mid_price = (min(rock_order_depth.buy_orders.keys()) + max(rock_order_depth.sell_orders.keys())) / 2
            rock_position = state.position.get(Product.VOLCANIC_ROCK, 0)
            current_round = getattr(state, "current_round", 1)

            # Generate stop loss and mean reversion orders for the underlying.
            stop_loss = self.stop_loss_orders(Product.VOLCANIC_ROCK, rock_order_depth, rock_position, rock_mid_price, traderData)
            mean_rev_orders = self.mean_reversion_orders(Product.VOLCANIC_ROCK, rock_order_depth, rock_position, rock_mid_price, traderData)
            if stop_loss:
                candidate_hedge_orders.extend(stop_loss)
            if mean_rev_orders:
                candidate_hedge_orders.extend(mean_rev_orders)
            
            # Process voucher orders for VOLCANIC_ROCK_VOUCHER_9500 if present.
            if Product.VOLCANIC_ROCK_VOUCHER_9500 in state.order_depths:
                voucher_order_depth = state.order_depths[Product.VOLCANIC_ROCK_VOUCHER_9500]
                voucher_position = state.position.get(Product.VOLCANIC_ROCK_VOUCHER_9500, 0)
                voucher_mid_price = self.get_voucher_mid_price(voucher_order_depth, traderData[Product.VOLCANIC_ROCK_VOUCHER_9500])
                if "entry_price" not in traderData[Product.VOLCANIC_ROCK_VOUCHER_9500]:
                    traderData[Product.VOLCANIC_ROCK_VOUCHER_9500]["entry_price"] = voucher_mid_price
                tte = self._calc_time_to_expiry(Product.VOLCANIC_ROCK_VOUCHER_9500, current_round)
                strike = self.params[Product.VOLCANIC_ROCK_VOUCHER_9500]["strike"]

                volatility = BlackScholes.implied_volatility(
                    voucher_mid_price, rock_mid_price, strike, tte
                )
                delta = BlackScholes.delta(rock_mid_price, strike, tte, volatility)
                voucher_take_orders, voucher_make_orders = self.voucher_orders(
                    voucher_order_depth, voucher_position, traderData[Product.VOLCANIC_ROCK_VOUCHER_9500], volatility,
                    Product.VOLCANIC_ROCK_VOUCHER_9500
                )
                rock_orders = self.volcanic_rock_hedge_orders(
                    rock_order_depth, voucher_order_depth, voucher_take_orders, rock_position, voucher_position, delta
                )
                if voucher_take_orders is not None or voucher_make_orders is not None:
                    result[Product.VOLCANIC_ROCK_VOUCHER_9500] = (voucher_take_orders or []) + (voucher_make_orders or [])
                if rock_orders is not None:
                    candidate_hedge_orders.extend(rock_orders)
            
            # Process voucher orders for VOLCANIC_ROCK_VOUCHER_9750 if present.
            if Product.VOLCANIC_ROCK_VOUCHER_9750 in state.order_depths:
                voucher_order_depth = state.order_depths[Product.VOLCANIC_ROCK_VOUCHER_9750]
                voucher_position = state.position.get(Product.VOLCANIC_ROCK_VOUCHER_9750, 0)
                voucher_mid_price = self.get_voucher_mid_price(voucher_order_depth, traderData[Product.VOLCANIC_ROCK_VOUCHER_9750])
                if "entry_price" not in traderData[Product.VOLCANIC_ROCK_VOUCHER_9750]:
                    traderData[Product.VOLCANIC_ROCK_VOUCHER_9750]["entry_price"] = voucher_mid_price
                tte = self._calc_time_to_expiry(Product.VOLCANIC_ROCK_VOUCHER_9750, current_round)
                strike = self.params[Product.VOLCANIC_ROCK_VOUCHER_9750]["strike"]

                volatility = BlackScholes.implied_volatility(
                    voucher_mid_price, rock_mid_price, strike, tte
                )
                delta = BlackScholes.delta(rock_mid_price, strike, tte, volatility)
                voucher_take_orders, voucher_make_orders = self.voucher_orders(
                    voucher_order_depth, voucher_position, traderData[Product.VOLCANIC_ROCK_VOUCHER_9750], volatility,
                    Product.VOLCANIC_ROCK_VOUCHER_9750
                )
                rock_orders = self.volcanic_rock_hedge_orders(
                    rock_order_depth, voucher_order_depth, voucher_take_orders, rock_position, voucher_position, delta
                )
                if voucher_take_orders is not None or voucher_make_orders is not None:
                    result[Product.VOLCANIC_ROCK_VOUCHER_9750] = (voucher_take_orders or []) + (voucher_make_orders or [])
                if rock_orders is not None:
                    candidate_hedge_orders.extend(rock_orders)
            
            if Product.VOLCANIC_ROCK_VOUCHER_10000 in state.order_depths:
                voucher_order_depth = state.order_depths[Product.VOLCANIC_ROCK_VOUCHER_10000]
                voucher_position = state.position.get(Product.VOLCANIC_ROCK_VOUCHER_10000, 0)
                voucher_mid_price = self.get_voucher_mid_price(voucher_order_depth, traderData[Product.VOLCANIC_ROCK_VOUCHER_10000])
                if "entry_price" not in traderData[Product.VOLCANIC_ROCK_VOUCHER_10000]:
                    traderData[Product.VOLCANIC_ROCK_VOUCHER_10000]["entry_price"] = voucher_mid_price
                tte = self._calc_time_to_expiry(Product.VOLCANIC_ROCK_VOUCHER_10000, current_round)
                strike = self.params[Product.VOLCANIC_ROCK_VOUCHER_10000]["strike"]

                volatility = BlackScholes.implied_volatility(
                    voucher_mid_price, rock_mid_price, strike, tte
                )
                delta = BlackScholes.delta(rock_mid_price, strike, tte, volatility)
                voucher_take_orders, voucher_make_orders = self.voucher_orders(
                    voucher_order_depth, voucher_position, traderData[Product.VOLCANIC_ROCK_VOUCHER_10000], volatility,
                    Product.VOLCANIC_ROCK_VOUCHER_10000
                )
                rock_orders = self.volcanic_rock_hedge_orders(
                    rock_order_depth, voucher_order_depth, voucher_take_orders, rock_position, voucher_position, delta
                )
                if voucher_take_orders is not None or voucher_make_orders is not None:
                    result[Product.VOLCANIC_ROCK_VOUCHER_10000] = (voucher_take_orders or []) + (voucher_make_orders or [])
                if rock_orders is not None:
                    candidate_hedge_orders.extend(rock_orders)
            
            if Product.VOLCANIC_ROCK_VOUCHER_10250 in state.order_depths:
                voucher_order_depth = state.order_depths[Product.VOLCANIC_ROCK_VOUCHER_10250]
                voucher_position = state.position.get(Product.VOLCANIC_ROCK_VOUCHER_10250, 0)
                voucher_mid_price = self.get_voucher_mid_price(voucher_order_depth, traderData[Product.VOLCANIC_ROCK_VOUCHER_10250])
                if "entry_price" not in traderData[Product.VOLCANIC_ROCK_VOUCHER_10250]:
                    traderData[Product.VOLCANIC_ROCK_VOUCHER_10250]["entry_price"] = voucher_mid_price
                tte = self._calc_time_to_expiry(Product.VOLCANIC_ROCK_VOUCHER_10250, current_round)
                strike = self.params[Product.VOLCANIC_ROCK_VOUCHER_10250]["strike"]

                volatility = BlackScholes.implied_volatility(
                    voucher_mid_price, rock_mid_price, strike, tte
                )
                delta = BlackScholes.delta(rock_mid_price, strike, tte, volatility)
                voucher_take_orders, voucher_make_orders = self.voucher_orders(
                    voucher_order_depth, voucher_position, traderData[Product.VOLCANIC_ROCK_VOUCHER_10250], volatility,
                    Product.VOLCANIC_ROCK_VOUCHER_10250
                )
                rock_orders = self.volcanic_rock_hedge_orders(
                    rock_order_depth, voucher_order_depth, voucher_take_orders, rock_position, voucher_position, delta
                )
                if voucher_take_orders is not None or voucher_make_orders is not None:
                    result[Product.VOLCANIC_ROCK_VOUCHER_10250] = (voucher_take_orders or []) + (voucher_make_orders or [])
                if rock_orders is not None:
                    candidate_hedge_orders.extend(rock_orders)

            if Product.VOLCANIC_ROCK_VOUCHER_10500 in state.order_depths:
                voucher_order_depth = state.order_depths[Product.VOLCANIC_ROCK_VOUCHER_10500]
                voucher_position = state.position.get(Product.VOLCANIC_ROCK_VOUCHER_10500, 0)
                voucher_mid_price = self.get_voucher_mid_price(voucher_order_depth, traderData[Product.VOLCANIC_ROCK_VOUCHER_10500])
                if "entry_price" not in traderData[Product.VOLCANIC_ROCK_VOUCHER_10500]:
                    traderData[Product.VOLCANIC_ROCK_VOUCHER_10500]["entry_price"] = voucher_mid_price
                tte = self._calc_time_to_expiry(Product.VOLCANIC_ROCK_VOUCHER_10500, current_round)
                strike = self.params[Product.VOLCANIC_ROCK_VOUCHER_10500]["strike"]

                volatility = BlackScholes.implied_volatility(
                    voucher_mid_price, rock_mid_price, strike, tte
                )
                delta = BlackScholes.delta(rock_mid_price, strike, tte, volatility)
                voucher_take_orders, voucher_make_orders = self.voucher_orders(
                    voucher_order_depth, voucher_position, traderData[Product.VOLCANIC_ROCK_VOUCHER_10500], volatility,
                    Product.VOLCANIC_ROCK_VOUCHER_10500
                )
                rock_orders = self.volcanic_rock_hedge_orders(
                    rock_order_depth, voucher_order_depth, voucher_take_orders, rock_position, voucher_position, delta
                )
                if voucher_take_orders is not None or voucher_make_orders is not None:
                    result[Product.VOLCANIC_ROCK_VOUCHER_10500] = (voucher_take_orders or []) + (voucher_make_orders or [])
                if rock_orders is not None:
                    candidate_hedge_orders.extend(rock_orders)
            
            # Instead of keeping only one best hedge order, add all candidate hedge orders.
            if candidate_hedge_orders:
                result.setdefault(Product.VOLCANIC_ROCK, []).extend(candidate_hedge_orders)

        traderDataEncoded = jsonpickle.encode(traderData)
        return result, 0, traderDataEncoded
