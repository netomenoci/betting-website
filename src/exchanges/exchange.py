
from abc import ABC, abstractmethod
from src.utils import Order
from typing import List, Union
from numpy import array, array_equal

class BookNormalized:
    def __init__(self, market_id : str, back_prices : List[array], back_sizes : List[array], lay_prices : List[array], lay_sizes: List[array], selection_ids : List[int]):
        """
        :param market_id: Uniquely identify the market
        :param selection_ids:List[int]: Store the selection ids for each runner in the market


        :param back_prices:List[array]: See below
        :param back_sizes:List[array]: See below
        :param lay_prices:List[array]: See below
        :param lay_sizes:List[array]:See below
        Each one of these lists contain orderbook_levels numpy arrays corresponding to each level of the book.
        Each numpy array contains len(selection_ids) elements, corresponding to each selection (price or size) in that level
        The first array corresponds to the level 0 , and the last element to the level orderbook_levels

        Example:
        Suppose the book contains the following three selections with the respective available to back and lay
            Selection id:  48317
            Available to back: [{'price': 12.0, 'size': 1951.39}, {'price': 11.5, 'size': 2352.28}, {'price': 11.0, 'size': 2338.73}]
            Available to lay: [{'price': 12.5, 'size': 2982.1}, {'price': 13.0, 'size': 3362.47}, {'price': 13.5, 'size': 2537.26}]

            Selection id:  47999
            Available to back: [{'price': 1.29, 'size': 30254.92}, {'price': 1.28, 'size': 28822.63}, {'price': 1.27, 'size': 46545.62}]
            Available to lay: [{'price': 1.3, 'size': 23428.33}, {'price': 1.31, 'size': 18059.1}, {'price': 1.32, 'size': 28868.98}]

            Selection id:  58805
            Available to back: [{'price': 7.0, 'size': 2664.64}, {'price': 6.8, 'size': 2022.21}, {'price': 6.6, 'size': 4552.72}]
            Available to lay: [{'price': 7.2, 'size': 5420.45}, {'price': 7.4, 'size': 3651.42}, {'price': 7.6, 'size': 3459.92}]

        The normalized orderbook representation (for two levels of the orderbook) would be:

            expected_parsed_book = (
                [array([12., 1.29, 7.]), array([11.5, 1.28, 6.8])],                             <- back prices
                [array([1951.39, 30254.92, 2664.64]), array([2352.28, 28822.63, 2022.21])],     <- back sizes
                [array([12.5, 1.3, 7.2]), array([13., 1.31, 7.4])],                             <- lay prices
                [array([2982.1, 23428.33, 5420.45]), array([3362.47, 18059.1, 3651.42])]        <- lay sizes
            )

        :return: The object itself
        """

        self._market_id = market_id
        self._selection_ids = selection_ids
        self._back_prices, self._back_sizes, self._lay_prices, self._lay_sizes = back_prices, back_sizes, lay_prices, lay_sizes
        self._levels_qty = len(self._back_prices)
        self._selections_qty = len(self._selection_ids)

    #TODO : Find a way to protect all these attributes from being eddited

    @property
    def market_id(self) -> str:
        return self._market_id

    @property
    def selection_ids(self) -> List[int]:
        return self._selection_ids

    @property
    def back_prices(self) -> List[array]:
        return self._back_prices
    @property
    def back_sizes(self) -> List[array]:
        return self._back_sizes

    @property
    def lay_prices(self) -> List[array]:
        return self._lay_prices

    @property
    def lay_sizes(self) -> List[array]:
        return self._lay_sizes
    @property
    def levels_qty(self) -> int:
        return self._levels_qty

    @property
    def selections_qty(self) -> int:
        return self._selections_qty

    def __eq__(self, other : "BookNormalized"):
        return len(self.back_prices) == len(other.back_prices) and \
            len(self.back_sizes) == len(other.back_sizes) and \
            len(self.lay_prices) == len(other.lay_prices) and \
            len(self.lay_sizes) == len(other.lay_sizes) and \
            all(array_equal(self.back_prices[i], other.back_prices[i]) for i in range(len(self.back_prices))) and \
            all(array_equal(self.back_sizes[i], other.back_sizes[i]) for i in range(len(self.back_sizes))) and \
            all(array_equal(self.lay_prices[i], other.lay_prices[i]) for i in range(len(self.lay_prices))) and \
            all(array_equal(self.lay_sizes[i], other.lay_sizes[i]) for i in range(len(self.lay_sizes)))

class Exchange(ABC):
    @abstractmethod
    def normalize_order(**kwargs) -> Union[Order, List[Order]]:
        pass
    @abstractmethod
    def normalize_book(**kwargs) -> BookNormalized:
        pass