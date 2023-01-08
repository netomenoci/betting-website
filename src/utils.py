from typing import List, Dict, Literal, Tuple
class Order:

    def __init__(self, market_id=None, runner_id=None, price=None, size_remaining=0, size_matched=0, side=None, bet_id=None, **kwargs):
        self.market_id = market_id
        self.runner_id = runner_id
        self.price = price
        self.size_remaining = size_remaining
        self.size_matched = size_matched
        self.side = side
        self.bet_id = bet_id
        self.__dict__.update(kwargs)

    def __repr__(self):
        return str(self.__dict__)

    def __eq__(self, other):
        return self.price == other.price and self.size_remaining == other.size_remaining and self.side == other.side and \
               self.market_id == other.market_id and self.runner_id == other.runner_id

class Market:

    def __init__(self, market_id, start_time, volume_matched, runners):
        self.market_id = market_id
        self.start_time = start_time
        self.volume_matched = volume_matched
        self.runners = runners


class Runner:

    def __init__(self, runner_id, available_to_back, available_to_lay):
        self.runner_id = runner_id
        self.available_to_back = available_to_back
        self.available_to_lay = available_to_lay


def get_login_details(path):
    f = open(path, "r")
    lines = f.readlines()
    f.close()
    return [line.strip() for line in lines]


def calc_matched_amount(matched_orders_market, selection_id, side):
    matched_orders_by_selection_and_side = matched_orders_market.get(selection_id, {}).get(side, [])
    return sum([order.size_matched for order in matched_orders_by_selection_and_side])

def split_matched_and_open(current_orders):

    open_orders = {}
    matched_orders = {}

    for current_order in current_orders:

        market_id = current_order.market_id
        runner_id = current_order.runner_id
        side = current_order.side.upper()

        if current_order.size_remaining > 0:

            if market_id not in open_orders:
                open_orders[market_id] = {}
            if runner_id not in open_orders[market_id]:
                open_orders[market_id][runner_id] = []

            open_orders[market_id][runner_id].append(current_order)

        if current_order.size_matched > 0:

            if market_id not in matched_orders:
                matched_orders[market_id] = {}
            if runner_id not in matched_orders[market_id]:
                matched_orders[market_id][runner_id] = {'BACK': [], 'LAY': []}

            matched_orders[market_id][runner_id][side].append(current_order)

    return matched_orders, open_orders

def get_pnl_outcomes(matched_orders_market : Dict[int, List[Order]], selection_ids : List[int]) -> Dict[int, float]:
    """
    The get_pnl_outcomes function takes in a dictionary of matched orders and returns the pnl for each selection.
    The function also takes in a list of selections to be considered, which is used to determine if there are complementary positions on other selections
    The function will return only one key-value pair with the total pnl for that selection.

    :param matched_orders_market:Dict[str: Store the matched orders for each selection
    :param List[Order]]: Store the matched orders for each selection
    :param selection_ids:List[str]: Specify the selection_ids of the selections we want to compute the pnl for
    :return: A dictionary with the pnl of each selection and a complementary pnl if there is only one selection
    """
    pnl_selections = {}
    for selection_i in selection_ids:
        pnl_selection = 0
        for selection_j, back_lay_orders in matched_orders_market.items():
            if selection_i == selection_j:  # position on the winning selection
                pnl_selection += sum([(x.price - 1) * x.size_matched for x in back_lay_orders["BACK"]]) - sum([(x.price - 1) * x.size_matched for x in back_lay_orders["LAY"]])
            else:  # Winning selection diffrent from position selection or single selection
                pnl_selection += sum(x.size_matched for x in back_lay_orders["LAY"]) - sum(x.size_matched for x in back_lay_orders["BACK"])
        pnl_selections[selection_i] = pnl_selection
    if len(selection_ids) == 1:
        positions_selection = matched_orders_market[selection_ids[0]]
        pnl_selections["complementary"] = sum(x.size_matched for x in positions_selection["LAY"]) - sum(x.size_matched for x in positions_selection["BACK"])
    return pnl_selections