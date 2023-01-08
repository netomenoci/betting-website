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

st.set_page_config(page_title="CRBMNC - BETTING HEDGE FUND", page_icon="₿", layout="wide")
st.title("CRBMNC - BETTING HEDGE FUND")

trading = Betfair()
trading.login()

# @st.cache(ttl=60 * 2)
def update_stats():
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

# Total Balance
st.subheader(f"Available to bet funds: {available_to_bet_balance}")
st.subheader(f"Expected pnl before cashout: {round(expected_pnl_before.sum(),2)}")
st.subheader(f"Expected pnl after cashout: {round(expected_pnl_after.sum(),2)}")
st.subheader(f"Hit ratio (before cashout): {100*round((expected_pnl_before > 0).mean(),3)}%")
st.subheader(f"Hit ratio (after cashout): {100*round((expected_pnl_after > 0).mean(),3)}%")


f"Selection stats"
selection_stats

f"-------------------"

f"Market Stats"
market_stats


market_id_filter = st.selectbox("Select the market_id", pd.unique(orders_df["market_id"]))
placeholder = st.empty()
orders_market = orders_df[orders_df["market_id"] == market_id_filter]
with placeholder.container():
    st.subheader("Orders per market")
    st.write(orders_market)