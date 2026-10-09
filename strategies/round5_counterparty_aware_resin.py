from datamodel import OrderDepth, TradingState, Order, Trade
from typing import List, Dict
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
        self.iceberg_orders: Dict[str, Dict[str, int]] = {}

    def take_orders(
        self, product: str, order_depth: OrderDepth, fair_value: int,
        take_width: float, position: int
    ) -> (List[Order], int, int):
        # unchanged
        orders: List[Order] = []
        buy_vol = 0
        sell_vol = 0
        if order_depth.sell_orders:
            best_ask = min(order_depth.sell_orders)
            vol = order_depth.sell_orders[best_ask]
            if best_ask < fair_value - take_width:
                qty = min(-vol, self.LIMIT[product] - position)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_vol += qty
        if order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders)
            vol = order_depth.buy_orders[best_bid]
            if best_bid > fair_value + take_width:
                qty = min(vol, self.LIMIT[product] + position)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_vol += qty
        return orders, buy_vol, sell_vol

    def clear_orders(
        self, product: str, order_depth: OrderDepth, fair_value: int,
        clear_width: int, position: int, buy_vol: int, sell_vol: int
    ) -> (List[Order], int, int):
        # unchanged
        orders: List[Order] = []
        pos_after = position + buy_vol - sell_vol
        fair_bid = fair_value - clear_width
        fair_ask = fair_value + clear_width
        if pos_after > 0:
            for price, vol in order_depth.buy_orders.items():
                if price >= fair_ask:
                    qty = min(vol, pos_after)
                    orders.append(Order(product, price, -qty))
                    sell_vol += qty
                    pos_after -= qty
                    if pos_after <= 0:
                        break
        elif pos_after < 0:
            for price, vol in order_depth.sell_orders.items():
                if price <= fair_bid:
                    qty = min(-vol, -pos_after)
                    orders.append(Order(product, price, qty))
                    buy_vol += qty
                    pos_after += qty
                    if pos_after >= 0:
                        break
        return orders, buy_vol, sell_vol

    def make_orders(
        self, product: str, order_depth: OrderDepth, fair_value: int,
        position: int, buy_vol: int, sell_vol: int, default_edge: float
    ) -> (List[Order], int, int):
        # unchanged
        orders: List[Order] = []
        pos_after = position + buy_vol - sell_vol
        mm_bid = fair_value - default_edge
        mm_ask = fair_value + default_edge
        iceberg_vis = self.params[product]["iceberg_visible"]
        # buy side
        buy_qty = self.LIMIT[product] - pos_after
        if buy_qty > 0:
            vis = min(buy_qty, iceberg_vis)
            rem = buy_qty - vis
            if rem > 0:
                self.iceberg_orders.setdefault(product, {"buy":0, "sell":0})
                self.iceberg_orders[product]["buy"] += rem
            orders.append(Order(product, mm_bid, vis))
            buy_vol += vis
        # sell side
        sell_qty = self.LIMIT[product] + pos_after
        if sell_qty > 0:
            vis = min(sell_qty, iceberg_vis)
            rem = sell_qty - vis
            if rem > 0:
                self.iceberg_orders.setdefault(product, {"buy":0, "sell":0})
                self.iceberg_orders[product]["sell"] += rem
            orders.append(Order(product, mm_ask, -vis))
            sell_vol += vis
        return orders, buy_vol, sell_vol

    def replenish_iceberg_orders(self, product: str, fair_value: int) -> List[Order]:
        orders: List[Order] = []
        if product not in self.iceberg_orders:
            return orders
        vis = self.params[product]["iceberg_visible"]
        edge = self.params[product]["default_edge"]
        if self.iceberg_orders[product]["buy"] > 0:
            qty = min(vis, self.iceberg_orders[product]["buy"])
            orders.append(Order(product, fair_value - edge, qty))
            self.iceberg_orders[product]["buy"] -= qty
        if self.iceberg_orders[product]["sell"] > 0:
            qty = min(vis, self.iceberg_orders[product]["sell"])
            orders.append(Order(product, fair_value + edge, -qty))
            self.iceberg_orders[product]["sell"] -= qty
        return orders

    def run(self, state: TradingState):
        # 1) decode persistent data
        data = jsonpickle.decode(state.traderData) if state.traderData else {}
        cp = data.setdefault("cp_stats", {})

        # 2) generate base orders
        result: Dict[str, List[Order]] = {}
        product = Product.RESIN
        if product in state.order_depths:
            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            fv = self.params[product]["fair_value"]
            tw = self.params[product]["take_width"]
            cw = self.params[product]["clear_width"]
            de = self.params[product]["default_edge"]

            take, buy_vol, sell_vol = self.take_orders(product, od, fv, tw, pos)
            clear, buy_vol, sell_vol = self.clear_orders(product, od, fv, cw, pos, buy_vol, sell_vol)
            make, buy_vol, sell_vol = self.make_orders(product, od, fv, pos, buy_vol, sell_vol, de)
            ice = self.replenish_iceberg_orders(product, fv)

            orders = take + clear + make + ice

            # 3) track Gary PnL from own_trades
            for sym, fills in state.own_trades.items():
                if sym != product: continue
                for tr in fills:
                    if tr.buyer == "SUBMISSION": cp_user = tr.seller
                    elif tr.seller == "SUBMISSION": cp_user = tr.buyer
                    else: continue
                    if cp_user != "Gary": continue
                    stats = cp.setdefault("Gary", {"vol":0, "pnl":0.0})
                    v = abs(tr.quantity)
                    stats["vol"] += v
                    stats["pnl"] += -tr.quantity * (tr.price - fv)

            # 4) tighten spread if Gary profitable
            pnl = cp.get("Gary", {}).get("pnl", 0.0)
            if pnl > 0:
                mm_bid = int(fv - de + 1)
                mm_ask = int(fv + de - 1)
            else:
                mm_bid = int(fv - de)
                mm_ask = int(fv + de)
            # replace first two mm orders if exist
            if orders:
                # assume first two are our mm orders
                orders[0] = Order(product, mm_bid, orders[0].quantity)
                if len(orders) > 1:
                    orders[1] = Order(product, mm_ask, orders[1].quantity)

            # 5) add Gary trades from market_trades
            buy_used = sum(o.quantity for o in orders if o.quantity>0)
            sell_used = sum(-o.quantity for o in orders if o.quantity<0)
            for tr in state.market_trades.get(product, []):
                price = int(tr.price)
                if tr.buyer == "Gary":
                    cap = self.LIMIT[product] + pos - sell_used
                    q = min(max(0, cap), tr.quantity)
                    if q>0:
                        orders.append(Order(product, price, -q))
                        sell_used += q
                        pos -= q
                elif tr.seller == "Gary":
                    cap = self.LIMIT[product] - pos - buy_vol
                    q = min(max(0, cap), tr.quantity)
                    if q>0:
                        orders.append(Order(product, price, q))
                        buy_vol += q
                        pos += q

            result[product] = orders

        # 6) persist and return
        enc = jsonpickle.encode(data)
        return result, 0, enc