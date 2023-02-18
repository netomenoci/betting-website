import sys
import os

# getting the name of the directory
# where the this file is present.
current = os.path.dirname(os.path.realpath(__file__))
# Getting the parent directory name
# where the current directory is present.
parent = os.path.dirname(current)
# adding the parent directory to
# the sys.path.
sys.path.append(parent)

import streamlit as st
from src.exchanges.betfair import Betfair
from src.utils import split_matched_and_open
from src.website_utils import get_selection_stats, get_market_stats
import pandas as pd
import time
from datetime import datetime


st.set_page_config(page_title="CRBMNC - BETTING HEDGE FUND", page_icon="₿", layout="wide")
st.title("CRBMNC - BETTING HEDGE FUND")

trading = Betfair()
trading.login()

# @st.cache(ttl=60*5)
def update_stats():
    f"Last time refreshed : {datetime.utcnow()}"
    data_load_state = st.text("Loading data from exchange...")
    account_funds = trading.trading.account.get_account_funds()
    available_to_bet_balance = account_funds.available_to_bet_balance

    orders = trading.get_current_orders()
    orders_df = pd.DataFrame([order.__dict__ for order in orders])
    matched_orders, open_orders = split_matched_and_open(orders)

    selection_stats = get_selection_stats(orders_df)
    market_id = pd.Series(selection_stats.index).apply(lambda x: x[0])
    selection_id = pd.Series(selection_stats.index).apply(lambda x: x[1])
    selection_stats.reset_index(inplace= True, drop = True)
    selection_stats['market_id'] = market_id
    selection_stats['selection_id'] = selection_id

    market_ids_matched = list(selection_stats["market_id"].unique())

    market_stats = get_market_stats(trading=trading, market_ids=market_ids_matched, matched_orders=matched_orders,
                                    open_orders=open_orders)
    market_stats.index.name = "market_id"
    market_stats.reset_index(inplace=True,drop=False)

    expected_pnl_before = market_stats.expected_pnl_before
    expected_pnl_after = market_stats.expected_pnl_after
    data_load_state.text(f"Finished loading data from the exchange!")

    return orders_df, selection_stats, market_stats,  available_to_bet_balance, expected_pnl_before, expected_pnl_after


orders_df, selection_stats, market_stats,  available_to_bet_balance, expected_pnl_before, expected_pnl_after = update_stats()

account_stats = {
    "Available to bet" : round(available_to_bet_balance, 2),
    "Total matched LAY" :  round(selection_stats.LAY_SIZE_MATCHED.sum(),2),
    "Total BACK matched" : round(selection_stats.BACK_SIZE_MATCHED.sum(),2),
    "Expected pnl before cashout" : round(expected_pnl_before.sum(),2),
    "Expected pnl after cashout" : round(expected_pnl_after.sum(),2),
    "Hit ratio (before cashout) %" : 100*round((expected_pnl_before > 0).mean(),3),
    "Hit ratio (after cashout) %" : 100*round((expected_pnl_after > 0).mean(),3)
}

f"Account Stats"
st.write("Stats", account_stats)

f"Market Stats"
# Display the market stats dataframe
st.dataframe(market_stats)

f"-------------------"

filtered_dataframes = {}
for market_id in market_stats['market_id'].unique():
    filtered_selection_stats = selection_stats[selection_stats['market_id'] == market_id]
    filtered_orders_df = orders_df[orders_df['market_id'] == market_id]
    filtered_dataframes[market_id] = {'selection_stats': filtered_selection_stats, 'orders_df': filtered_orders_df}

def filter_dataframes(market_id):
    f"Selection stats"
    st.write(filtered_dataframes[market_id]['selection_stats'])
    f"Market orders"
    st.write(filtered_dataframes[market_id]['orders_df'])


market_id_filter = st.selectbox("Select the market_id", pd.unique(orders_df["market_id"]))
placeholder = st.empty()
with placeholder.container():
    st.subheader(f"Filtered for {market_id_filter}")
    filter_dataframes(market_id_filter)

# time.sleep(60*5)
# raise st.experimental_rerun()