import cvxpy as cp
import numpy as np
from collections import OrderedDict
from copy import deepcopy
from logzero import logger
from typing import List, Dict, Literal, Tuple
from src.utils import Order
from src.exchanges.exchange import BookNormalized
from src.utils import get_pnl_outcomes

class CashoutOutput:
    def __init__(self, orders = None, expected_pnl_before = None, expected_pnl_after = None, worst_outcome_before = None, worst_outcome_after = None):
        self.orders = orders
        self.expected_pnl_before = expected_pnl_before
        self.expected_pnl_after = expected_pnl_after
        self.worst_outcome_before = worst_outcome_before
        self.worst_outcome_after = worst_outcome_after

class Cashout:
    def __init__(self, market_book : BookNormalized, matched_orders : Dict[int, List[Order]],
                 open_orders: Dict[int, List[Order]], mode : Literal["maker", "taker"], constrain_by_volume : bool = True, max_std_allowed : float = 0.05):
        self.market_book = market_book
        self.matched_orders = self.fill_missing_selections(orders = matched_orders, selection_ids=self.market_book.selection_ids)
        self.open_orders = open_orders
        self.mode = mode
        self.max_std_allowed = max_std_allowed
        self.pnl_outcomes = get_pnl_outcomes(self.matched_orders, self.market_book.selection_ids)
        self.constrain_by_volume = constrain_by_volume
    def get_cashout_orders(self) -> List[Order]:
        """
        The get_cashout_orders function is called by the executioner to place orders on the market.
        It returns a list of orders that will neutralize all positions in order to bring them back into a balanced state.
        It checks if that market is already balanced before.
        :param self: Access the instance attributes of the class
        :return: A list of orders that will neutralize the current positions
        """
        # TODO: The orders executioner must be able to place small orders - Implement mechanism to do that

        # Return empty target orders list if it is already balanced
        logger.info(f"CASHOUT market {self.market_book.market_id}: {self.pnl_outcomes} are balanced. Exiting the program")


        logger.info(f"CASHOUT market {self.market_book.market_id}: {self.pnl_outcomes} are NOT balanced. Starting cashout")
        try:
            neutralizer_orders = self._get_neutralizer_orders_retry(max_std_allowed=self.max_std_allowed)
        except Exception as e:
            print(f"CASHOUT - Failed  {e}")

        # print(f"CASHOUT: Neutralizer orders: {neutralizer_orders}")
        if neutralizer_orders is None:
            logger.info("Constraints dont allow for a cashout solution ")
        return neutralizer_orders

    def _get_neutralizer_orders_retry(self, max_std_allowed) -> List[Order]:
        if max_std_allowed > 10:
            print(f"CASHOUT - max_std_allowed is above 10 {max_std_allowed}. Returning no orders to cashout")
            return None
        try:
            return self._get_neutralizer_orders(max_std_allowed=max_std_allowed)
        except Exception as e:
            print(f"CASHOUT - Failed with max_std = {max_std_allowed} : {e}. Retry with double the value")
            return self._get_neutralizer_orders_retry(max_std_allowed=2*max_std_allowed)


    def _get_neutralizer_orders(self, max_std_allowed = None) -> CashoutOutput:
        """
        The _get_neutralizer_orders_single_selection function is a helper function that returns the orders to neutralize the position of in a market.
        It does that by maximizin the expected pnl subject to constraints on the standard deviation of the selections outcomes.
        It takes as input:
        - self, which is an instance of Cashout. It contains all information about the pnl outcomes and market book data needed to generate orders.
        It also contains other information such as pnl outcomes and mode (taker or maker).

        :param self: Access the variables and methods of the class in which it is used
        :return: A list of orders
        """
        if max_std_allowed is None:
            max_std_allowed = self.max_std_allowed

        book_back_prices = deepcopy(self.market_book.back_prices)
        book_lay_prices = deepcopy(self.market_book.lay_prices)
        # TODO: Add a check not to cashout if pnl is too much degradeted
        # TODO: Add mechanism to zero small orders before computing actual pnl
        # TODO: Add a mechanism to retry the optimization with a less rigid constraint on variance

        if self.market_book.selections_qty == 1:
            parsed_orders = self._get_neutralizer_orders_single_selection()
            return parsed_orders

        # This will handle the vector of optimal stakes
        x = cp.Variable(2 * self.market_book.selections_qty * self.market_book.levels_qty)

        pnl_selections_current = np.array([self.pnl_outcomes[selection] for selection in self.market_book.selection_ids])
        prob_selections = 0.5 / (book_back_prices[0]) + 0.5 / (book_lay_prices[0])
        expected_pnl_current = pnl_selections_current @ prob_selections.T

        # Remove 1 from odds
        for i in range(self.market_book.levels_qty):
            book_back_prices[i] -= 1
            book_lay_prices[i] -= 1

        # Compute M matrix that computes pnl for different selection_id outcomes
        M = []
        for level in range(self.market_book.levels_qty):
            back_diag = -1 * np.ones((self.market_book.selections_qty, self.market_book.selections_qty))
            np.fill_diagonal(back_diag, book_back_prices[level])

            lay_diag = np.ones((self.market_book.selections_qty, self.market_book.selections_qty))
            np.fill_diagonal(lay_diag, -book_lay_prices[level])
            M_level = np.concatenate((back_diag, lay_diag), axis=1)
            M.append(M_level)
        M = np.concatenate(M, axis=1)
        pnl_selections_delta = M @ x

        pnl_selections_new = pnl_selections_delta + pnl_selections_current
        expected_pnl_new = pnl_selections_new @ prob_selections

        variability = pnl_selections_new - cp.sum(pnl_selections_new)/self.market_book.selections_qty
        variance = cp.norm(variability)

        constraints = [x >= 0]
        if self.constrain_by_volume:
            size_constraints = self.create_bounds(x)
            constraints.extend(size_constraints)

        constraints.append((variance <= max_std_allowed))
        objective = cp.Minimize(-expected_pnl_new)
        prob = cp.Problem(objective, constraints)
        result = prob.solve()

        parsed_orders = self.vector_solution_to_orders(x.value)

        print(f"Expected PNL before: {expected_pnl_current}")
        print(f"expected PNL after ideal neutralization: {expected_pnl_new.value}")

        print(f"PNL selections before: {pnl_selections_current}")
        print(f"PNL selections after: {pnl_selections_new.value}")

        cashout_output = CashoutOutput(
            orders = parsed_orders,
            expected_pnl_before = expected_pnl_current,
            expected_pnl_after = expected_pnl_new.value,
            worst_outcome_before = min(self.pnl_outcomes.values()),
            worst_outcome_after = None,
        )

        return cashout_output

    def _get_neutralizer_orders_single_selection(self) -> List[Order]:
        """
        The _get_neutralizer_orders_single_selection function is a helper function that returns the orders to neutralize the position of a single selection.
        It takes as input:
        - self, which is an instance of Cashout. It contains all information about the pnl outcomes and market book data needed to generate orders.
        - selection_id, which is an integer representing the id of one specific runner in this market (e.g., if we are trading on Betfair's tennis markets, it could be 234567; for Roger Federer).
        It also contains other information such as pnl outcomes and mode (taker or maker).

        :param self: Access the variables and methods of the class in which it is used
        :return: A list of orders
        """

        # NO OPTIMIZATION USED HERE - PURE EQUILIBRIUM

        # TODO: Make it aware of sizes
        # TODO: Optimize in the expected_return constrained to variance framework

        selection_id = self.market_book.selection_ids[0]

        pnl_event_happen = self.pnl_outcomes[selection_id]
        pnl_not_happen = self.pnl_outcomes["complementary"]
        if pnl_event_happen > pnl_not_happen:
            if self.mode == "taker":
                best_lay_price = self.market_book.lay_prices[0][0]
            elif self.mode == "maker":
                best_lay_price = self.market_book.back_prices[0][0]
            else:
                raise Exception("mode must be taker or maker")
            qty_to_lay = (pnl_event_happen - pnl_not_happen) / best_lay_price
            lay_order = {"selection_id": selection_id, "side": "LAY", "price": best_lay_price, "size_remaining": qty_to_lay}
            return [Order(**lay_order)]
        else:
            if self.mode == "taker":
                best_back_price = self.market_book.back_prices[0][0]
            elif self.mode == "maker":
                best_back_price = self.market_book.lay_prices[0][0]
            else:
                raise Exception("mode must be taker or maker")
            qty_to_back = (pnl_not_happen - pnl_event_happen) / best_back_price
            back_order = {"selection_id": selection_id, "side": "BACK", "price": best_back_price, "size_remaining": qty_to_back}
            return [Order(**back_order)]

    @staticmethod
    def fill_missing_selections(orders : Dict[int, Dict], selection_ids : List[int]) -> Dict[int, Dict]:
        """
        The fill_missing_selections function fills in missing selection ids with empty lists.
        This is necessary because the orders dictionary is built from a list of order objects, which are not guaranteed to be
        in any particular order. This function ensures that all selection ids are accounted for and no data is lost.

        :param orders:Dict[int: Store the orders for each selection
        :param Dict]: Store the orders for each selection
        :param selection_ids:List[int]: Store a list of selection ids that are present in the orderbook
        :return: A dictionary of orderbooks with all the selections that are missing in each orderbook
        """
        orders = deepcopy(orders)
        missing_selection_positions = selection_ids - orders.keys()
        for selection_id in missing_selection_positions:
            orders[selection_id] = {"BACK": [], "LAY": []}
        orders = OrderedDict(sorted(orders.items()))
        return orders

    def create_bounds(self, x : np.array) -> List:
        """
        The create_bounds function takes in the following parameters:
            x : np.array
                The vector of variables that are going to be bounded by constraints.

        :param self: Access the variables and methods of the class in which it is used
        :param x:np.array: Specify the vector of variables that are going to be optimized
        :return: A list of constraints that ensure that the x vector is within the order limits
        """
        constraints = []
        for level in range(self.market_book.levels_qty):
            for selection_number in range(self.market_book.selections_qty):
                back_idx = 2 * level * self.market_book.selections_qty + selection_number
                lay_idx = (2 * level + 1) * self.market_book.selections_qty + selection_number

                back_order_cap = self.market_book.back_sizes[level][selection_number]
                lay_order_cap = self.market_book.lay_sizes[level][selection_number]

                constraints.append(x[back_idx] <= back_order_cap)
                constraints.append(x[lay_idx] <= lay_order_cap)
        return constraints

    def vector_solution_to_orders(self, opt_stake_array : np.array) -> List[Order]:
        """
        The vector_solution_to_orders function takes a vector of optimal stake values and converts it into an array of orders.
        The function is designed to work with the output from the optimisation functions in this module, which are themselves designed to solve
        the problem: given a set of market prices (back_prices, lay_prices) and a desired minimum variance in pnl outcomes, what are the optimal orders to optimize the expected pnl?
        The solution is found by minimising over all possible combinations of back/lay orders for each selection. The result is an array
        of optimal stakes for each combination - (SELECTION_ID, PRICE, SIDE), one per order. This function then converts that array into a list containing all orders

        """
        orders = []
        selections_qty = len(self.market_book.back_prices[0])
        levels_qty = len(self.market_book.back_prices)

        for level in range(levels_qty):
            for selection_number in range(selections_qty):
                selection_id = self.market_book.selection_ids[selection_number]
                back_idx = 2 * level * selections_qty + selection_number
                lay_idx = (2 * level + 1) * selections_qty + selection_number

                back_order_qty = opt_stake_array[back_idx]
                lay_order_qty = opt_stake_array[lay_idx]

                if self.mode == "taker":
                    back_order_px = self.market_book.back_prices[level][selection_number]
                    lay_order_px = self.market_book.lay_prices[level][selection_number]
                elif self.mode == "maker":
                    back_order_px = self.market_book.lay_prices[level][selection_number]
                    lay_order_px = self.market_book.back_prices[level][selection_number]
                else:
                    raise Exception("mode must be maker or taker")
                back_order = {"market_id" : self.market_book.market_id, "runner_id": selection_id, "side": "BACK", "price": back_order_px, "size_remaining": round(back_order_qty, 1)}
                lay_order = {"market_id" : self.market_book.market_id, "runner_id": selection_id, "side": "LAY", "price": lay_order_px, "size_remaining": round(lay_order_qty, 1)}
                orders.append(Order(**back_order))
                orders.append(Order(**lay_order))
        return orders

    def check_positions_balanced(self) -> bool:
        """
        The check_positions_balanced function checks whether the positions are balanced.
        It returns True if they are, and False otherwise.

        :param self: Access the instance attributes of the class
        :return: A boolean value
        """
        return np.std(list(self.pnl_outcomes.values())) <= self.max_std_allowed

