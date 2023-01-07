import os
import pandas as pd
import betfairlightweight
from betfairlightweight.filters import market_filter
from src.utils import Order, Market, Runner, split_matched_and_open, get_login_details
from src.exchanges.exchange import Exchange, BookNormalized
import numpy as np
# from tenacity import retry, wait_fixed, stop_after_attempt
from betfairlightweight.resources.bettingresources import MarketBook
from typing import Union, List


class Betfair(Exchange):

    def login(self):
        certs_path_betfair = os.getcwd() + "/src/credentials/betfair"
        username, password, app_key = get_login_details(os.getcwd() + "/src/credentials/betfair/credentials.txt")
        # certs_path_betfair = os.getcwd() + "/credentials/betfair"
        # username, password, app_key = get_login_details(os.getcwd() + "/credentials/betfair/credentials.txt")
        self.trading = betfairlightweight.APIClient(username=username, password=password, app_key=app_key, certs=certs_path_betfair)
        self.trading.login.connect_timeout = self.trading.login.read_timeout = 30
        self.trading.login()

    @staticmethod
    def normalize_order(order):
        return Order(order.market_id, order.selection_id, order.price_size.price, order.size_remaining, order.size_matched, order.side, order.bet_id)

    @staticmethod
    def normalize_book(book : MarketBook, orderbook_levels : int, selection_ids : Union[List[int], None] = None) -> BookNormalized:
        """
        The parse_book function takes a MarketBook object and returns four lists of numpy arrays.
        Each one of these list contains orderbook_levels numpy arrays corresponding to each level of the book.
        Each numpy array contains len(selection_ids) elements, corresponding to each selection (price or size) in that level
        The first array corresponds to the level 0 , and the last element to the level orderbook_levels

        :param book:MarketBook
        :param selection_ids:List[int]: Select which runners to include in the orderbook
        :param orderbook_levels:int=3: Specify the number of levels to return
        :return: The following:
        Four lists of numpy arrays
        The first list is the back prices for each runner in the book
        the second list is the back sizes for each runner in the book,
        the third list is the lay prices for each runner in the book, and
        the fourth list is teh lay sizes for each runner in teh book.

        """
        if selection_ids is None:
            selection_ids = [runner.runner_id for runner in book.runners]

        # TODO: Add specific exceptions
        book_back_prices = []
        book_back_sizes = []
        book_lay_prices = []
        book_lay_sizes = []

        book_selections = {}
        for runner in book.runners:
            selection_id = runner.runner_id
            book_selections[selection_id] = runner

        for level in range(orderbook_levels):
            book_back_prices_level = []
            book_back_sizes_level = []
            book_lay_prices_level = []
            book_lay_sizes_level = []
            for selection_id in selection_ids:
                try:
                    runner = book_selections[selection_id]
                except KeyError:
                    runner = None
                try:
                    available_to_back = runner.available_to_back[level]
                    price_back = available_to_back["price"]
                    size_back = available_to_back["size"]
                except:
                    price_back = 1.01
                    size_back = 0

                try:
                    available_to_lay = runner.available_to_lay[level]
                    price_lay = available_to_lay["price"]
                    size_lay = available_to_lay["size"]
                except:
                    price_lay = 1000
                    size_lay = 0

                book_back_prices_level.append(price_back)
                book_back_sizes_level.append(size_back)
                book_lay_prices_level.append(price_lay)
                book_lay_sizes_level.append(size_lay)

            book_back_prices.append(np.array(book_back_prices_level))
            book_back_sizes.append(np.array(book_back_sizes_level))
            book_lay_prices.append(np.array(book_lay_prices_level))
            book_lay_sizes.append(np.array(book_lay_sizes_level))

        return BookNormalized(market_id=book.market_id, back_prices=book_back_prices, back_sizes=book_back_sizes,
                              lay_prices=book_lay_prices, lay_sizes=book_lay_sizes, selection_ids=selection_ids)

    #@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
    def get_matched_and_open_orders(self):
        count = 0
        current_orders = []
        while True:
            current_orders_batch = self.trading.betting.list_current_orders(from_record=count * 1000, record_count=1000).orders
            current_orders.extend(current_orders_batch)
            if len(current_orders_batch) < 1000:
                break
        current_orders = [self.normalize_order(order) for order in current_orders]
        return split_matched_and_open(current_orders)

    #@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
    def get_market_books(self, market_ids):
        max_count = 40  # https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Market+Data+Request+Limits
        filter = betfairlightweight.filters.price_projection(price_data=['EX_BEST_OFFERS'], virtualise=True)
        markets = []
        for i in range(0, len(market_ids), max_count):
            markets.extend(self.trading.betting.list_market_book(market_ids=market_ids[i: i+max_count], price_projection=filter, lightweight=True))
        return markets

    #@retry(wait=wait_fixed(5), stop=stop_after_attempt(5))
    def _get_market_catalogue(self, event_type_id, market_type_code, min_volume):
        filter = market_filter(event_type_ids=[event_type_id], market_type_codes=[market_type_code])
        market_catalogue = self.trading.betting.list_market_catalogue(filter, lightweight=True, max_results=1000, market_projection=['MARKET_START_TIME'])
        return {x['marketId']: x for x in market_catalogue if x['totalMatched'] > min_volume}

    def get_market_catalogue(self, event_type_ids, market_type_codes, min_volume):
        market_catalogue = {}
        for event_type_id in event_type_ids:
            for market_type_code in market_type_codes:
                market_catalogue.update(self._get_market_catalogue(event_type_id, market_type_code, min_volume))
        return {k: v for k, v in market_catalogue.items() if v['totalMatched'] > min_volume}

    def get_markets(self, event_type_ids, market_type_codes, min_volume=1000):
        market_catalogue = self.get_market_catalogue(event_type_ids, market_type_codes, min_volume)
        market_books = self.get_market_books(list(market_catalogue.keys()))
        markets = []
        for market in market_books[:]:
            runners = []
            for runner in market['runners']:
                runner_id = runner['selectionId']
                available_to_back = runner['ex']['availableToBack']
                available_to_lay = runner['ex']['availableToLay']
                runners.append(Runner(runner_id, available_to_back, available_to_lay))
            if len(runners) > 0:
                start_time = pd.to_datetime(market_catalogue[market['marketId']]['marketStartTime']).timestamp()
                volume_matched = market_catalogue[market['marketId']]['totalMatched']
                markets.append(Market(market['marketId'], start_time, volume_matched, runners))

        return sorted(markets, key=lambda x: x.start_time)

    def cancel_limit_order(self, market_id, bet_id=None, size_reduction=None):
        instructions = [betfairlightweight.filters.cancel_instruction(bet_id=bet_id, size_reduction=size_reduction)] if bet_id else None
        response = self.trading.betting.cancel_orders(market_id=market_id, instructions=instructions, lightweight=True)
        return response

    def replace_limit_order(self, market_id, bet_id, new_price):
        instructions = betfairlightweight.filters.replace_instruction(bet_id=bet_id, new_price=new_price)
        response = self.trading.betting.replace_orders(market_id=market_id, instructions=[instructions], lightweight=True)
        return response

    def place_limit_order(self, market_id, selection_id, side, size, price, customer_strategy_ref=None):
        limit_order_filter = betfairlightweight.filters.limit_order(size=size, price=price, persistence_type='LAPSE')
        place_instructions = betfairlightweight.filters.place_instruction(selection_id=selection_id, order_type="LIMIT", side=side, limit_order=limit_order_filter)
        response = self.trading.betting.place_orders(market_id=market_id, instructions=[place_instructions], customer_strategy_ref=customer_strategy_ref, lightweight=True)
        return response

    def execute(self, orders_to_cancel, orders_to_replace, orders_to_place):

        for order in orders_to_cancel:
            try:
                resp = self.cancel_limit_order(order.market_id, order.bet_id)
                print(resp)
            except Exception as e:
                print(e)

        for order in orders_to_replace:
            try:
                resp = self.replace_limit_order(order.market_id, order.bet_id, order.price)
                print(resp)
            except Exception as e:
                print(e)

        for order in orders_to_place:
            try:
                resp = self.place_limit_order(order.market_id, order.runner_id, order.side, round(order.size_remaining, 1), order.price)
                print(resp)
            except Exception as e:
                print(e)

