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

#
# # Importando o objecto Fundo
# @st.cache
# def get_fund_object():
#     return Fund()
# fundo = get_fund_object()


# @st.cache(ttl=60 * 2)
def update_stats():
    data_load_state = st.text("Loading data from exchange...")
    account_funds = trading.trading.account.get_account_funds()
    available_to_bet_balance = account_funds.available_to_bet_balance

    orders = trading.get_current_orders()
    matched_orders, open_orders = split_matched_and_open(orders)

    selection_stats = get_selection_stats(orders)
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

    return selection_stats, market_stats,  available_to_bet_balance, expected_pnl_before, expected_pnl_after


selection_stats, market_stats,  available_to_bet_balance, expected_pnl_before, expected_pnl_after = update_stats()

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

#
# f"Total balance in {round(total_balance, 2)} {ASSET_QUOTE} evaluated at {now_brl} of Brazil time"
#
# placeholder = st.empty()
# with placeholder.container():
#     st.subheader("Quotas")
#     quotas_dict = fundo.get_quotas().iloc[-1].to_dict()
#     del quotas_dict["time"]
#     fig, ax = plt.subplots()
#     ax.pie(x=list(quotas_dict.values()), labels=list(quotas_dict.keys()),
#            autopct=lambda pct: "{:.2f} USDT".format(pct * total_balance / 100))
#     st.pyplot(fig, width=10)
#
# # Create a text element and let the reader know the data is loading.
# data_load_state = st.text("Loading trading history...")
#
#
# @st.cache(ttl=60 * 5)
# def update_historical_orders():
#     data = download_all_parquets_in_path(path="s3://cs-crypto/historical_orders/")
#     data["date"] = pd.to_datetime(data["datetime"]).dt.round(
#         "D")  # Cache variables should never change outside the function
#     data_time = datetime.now(pytz.timezone('Brazil/East')).replace(tzinfo=None)
#     return data, data_time
#
#
# data, data_time = update_historical_orders()
# data_load_state.text(f"Historical orders loaded at {data_time}!")
#
# placeholder = st.empty()
# with placeholder.container():
#     st.subheader("Transactions")
#     fig_col1, fig_col2 = st.columns(2)
#     with fig_col1:
#         st.markdown("### Buy and Sell transactions in USD over time")
#         transactions_pvt = get_transactions_pivoted(data)
#         st.write(transactions_pvt.plot())
#
# date_filter = st.selectbox("Select the trading date", pd.unique(data["date"]))
#
# # creating a single-element container.
# placeholder = st.empty()
#
# # dataframe filter
# data = data[data["date"] == date_filter]
# qty_currencies = data["symbol"].nunique()
#
# with placeholder.container():
#     st.subheader("Raw trading data")
#     st.write(data)
#
#     st.subheader("Quantity of trades")
#     st.write(data.groupby("side")["symbol"].nunique())
#
#     st.subheader("Transaction values in $US")
#     st.write(data.groupby("side")["cost"].sum())
#
#     kpi1, kpi2 = st.columns(2)
#     kpi1.metric(label="Quantity of unique currencies being traded ", value=f"{qty_currencies}")

# time.sleep(60 * 10)
# raise st.experimental_rerun()