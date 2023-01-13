import pandas as pd
import time
from typing import List
from src.utils_cashout import Cashout
import numpy as np

def get_market_stats(trading, market_ids: List[str], matched_orders, open_orders) -> pd.DataFrame:
    markets = trading.get_markets(event_type_ids=None,
                                  market_type_codes=['MATCH_ODDS', 'BOTH_TEAMS_TO_SCORE', 'OVER_UNDER_25'],
                                  min_volume=0,
                                  market_ids=market_ids
                                  )
    stats = {}
    for market in markets:
        print(f"Market id: {market.market_id}")
        market_stats = {}
        normalized_book = trading.normalize_book(market, orderbook_levels=1)
        matched_orders_market = matched_orders.get(market.market_id, {})
        open_orders_market = open_orders.get(market.market_id, {})
        cashout = Cashout(
            market_book=normalized_book,
            matched_orders=matched_orders_market,
            open_orders=open_orders_market,
            mode="taker",
            constrain_by_volume=False,
            max_std_allowed=1
        )

        hours_to_start = round((market.start_time - time.time()) / 3600,2)
        cashout_output = cashout._get_neutralizer_orders_retry(max_std_allowed=1)

        if cashout_output is not None:
            expected_pnl_before = round(cashout_output.expected_pnl_before,2)
            expected_pnl_after = round(cashout_output.expected_pnl_after,2)
            worst_outcome_before = round(cashout_output.worst_outcome_before, 2)
        else:
            expected_pnl_before = None
            expected_pnl_after = None
            worst_outcome_before = None

        market_stats["expected_pnl_before"] = expected_pnl_before
        market_stats["expected_pnl_after"] = expected_pnl_after
        market_stats["worst_outcome_before"] = worst_outcome_before
        market_stats["hours_to_start"] = hours_to_start
        stats[market.market_id] = market_stats

    market_stats = pd.DataFrame.from_records(stats).T

    return market_stats


def get_selection_stats(orders_df) -> pd.DataFrame:
    matched_orders_df = orders_df[orders_df["size_matched"] != 0]
    size_matched = matched_orders_df.groupby(["market_id", "runner_id", "side"])["size_matched"].sum().rename("size_matched").to_frame()
    size_matched = size_matched.reset_index(level = 2)
    size_matched = size_matched.pivot_table(index = size_matched.index, columns = "side", values = "size_matched")
    size_matched.columns = size_matched.columns + "_SIZE_MATCHED"

    avg_matched_price = matched_orders_df.groupby(["market_id", "runner_id", "side"]).apply(lambda g: np.average(g['price'], weights=g['size_matched']))
    avg_matched_price = avg_matched_price.rename("avg_price").to_frame()
    avg_matched_price = avg_matched_price.reset_index(level = 2)
    avg_matched_price = avg_matched_price.pivot_table(index = avg_matched_price.index, columns = "side", values = "avg_price")
    avg_matched_price.columns = avg_matched_price.columns + "_AVG_PRICE"
    matches_df = pd.concat([avg_matched_price, size_matched], axis = 1)

    return matches_df
