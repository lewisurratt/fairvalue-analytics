from __future__ import annotations

from datetime import datetime
from io import StringIO

import pandas as pd
import streamlit as st

from fairvalue.services.importer import normalize_trade_csv
from fairvalue.storage.base import DataRepository
from fairvalue.ui import empty_state, money, page_header, section


def _account_options(accounts: pd.DataFrame) -> dict[str, str]:
    options = {"": "Not linked"}
    options.update(
        {
            str(row["id"]): f"{row['prop_firm']} · {row['account_type']} · {str(row['id'])[:8]}"
            for _, row in accounts.iterrows()
        }
    )
    return options


def _upload(repo: DataRepository, accounts: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)
    source = col1.selectbox("Source format", ["Tradovate", "Lucid", "Generic CSV"])
    options = _account_options(accounts)
    account_id = col2.selectbox("Apply account", options, format_func=lambda value: options[value])
    uploaded = st.file_uploader("Trade export", type=["csv"], help="Completed trades or fill-level CSV data")
    if uploaded is None:
        st.caption("Recognizes common columns such as Symbol, Side, Qty, Entry/Exit Time, Price, P&L, and Fees.")
        return
    try:
        records = normalize_trade_csv(uploaded, source=source, default_account_id=account_id)
    except Exception as exc:
        st.error(f"Could not normalize this file: {exc}")
        return
    if not records:
        st.warning("No completed trades were found. Open positions are intentionally excluded.")
        return
    preview = pd.DataFrame(records)
    st.success(f"Found {len(preview)} completed trade{'s' if len(preview) != 1 else ''}.")
    st.dataframe(
        preview[["symbol", "side", "quantity", "entry_time", "exit_time", "entry_price", "exit_price", "net_pnl"]],
        hide_index=True,
        width="stretch",
    )
    col3, col4 = st.columns(2)
    strategy = col3.text_input("Apply strategy tag (optional)")
    setup = col4.text_input("Apply setup tag (optional)")
    if st.button("Import normalized trades", type="primary", width="stretch"):
        for record in records:
            if strategy.strip():
                record["strategy"] = strategy.strip()
            if setup.strip():
                record["setup"] = setup.strip()
        inserted, duplicates = repo.add_many_unique("trades", records, "trade_key")
        st.success(f"Imported {inserted} trade(s). Skipped {duplicates} duplicate(s).")


def _manual_trade(repo: DataRepository, accounts: pd.DataFrame) -> None:
    options = _account_options(accounts)
    with st.form("manual_trade", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        account_id = col1.selectbox("Account", options, format_func=lambda value: options[value])
        symbol = col2.text_input("Symbol", placeholder="NQ")
        side = col3.selectbox("Side", ["Long", "Short"])
        col4, col5, col6 = st.columns(3)
        quantity = col4.number_input("Quantity", min_value=0.01, value=1.0, step=1.0)
        entry_price = col5.number_input("Entry price", min_value=0.0, format="%.4f")
        exit_price = col6.number_input("Exit price", min_value=0.0, format="%.4f")
        col7, col8 = st.columns(2)
        entry_time = col7.text_input("Entry time", placeholder="2026-08-18 09:35:00")
        exit_time = col8.text_input("Exit time", placeholder="2026-08-18 09:42:00")
        col9, col10, col11 = st.columns(3)
        gross = col9.number_input("Gross P&L", step=25.0)
        fees = col10.number_input("Fees", min_value=0.0, step=1.0)
        strategy = col11.text_input("Strategy")
        setup = st.text_input("Setup")
        submitted = st.form_submit_button("Add trade", type="primary", width="stretch")
        if submitted:
            if not symbol.strip() or not entry_time.strip() or not exit_time.strip():
                st.error("Symbol, entry time, and exit time are required.")
                return
            raw = pd.DataFrame(
                [
                    {
                        "Symbol": symbol,
                        "Side": side,
                        "Quantity": quantity,
                        "Entry Time": entry_time,
                        "Exit Time": exit_time,
                        "Entry Price": entry_price,
                        "Exit Price": exit_price,
                        "Gross PnL": gross,
                        "Fees": fees,
                        "Strategy": strategy,
                        "Setup": setup,
                    }
                ]
            )
            records = normalize_trade_csv(StringIO(raw.to_csv(index=False)), "Manual", account_id)
            inserted, duplicates = repo.add_many_unique("trades", records, "trade_key")
            if inserted:
                st.success("Trade added.")
                st.rerun()
            else:
                st.warning(f"Trade matched {duplicates} existing record(s).")


def render(repo: DataRepository, demo_mode: bool) -> None:
    accounts = repo.list("accounts")
    trades = repo.list("trades")
    page_header(
        "Trade ingestion",
        "Import once. Analyze forever.",
        "Normalize completed trades and fill data into a durable schema with deterministic duplicate protection.",
    )
    upload_tab, manual_tab = st.tabs(["Upload CSV", "Add structured trade"])
    with upload_tab:
        _upload(repo, accounts)
    with manual_tab:
        _manual_trade(repo, accounts)

    section("Imported trades")
    trades = repo.list("trades")
    if trades.empty:
        empty_state("No trades yet. Upload a Tradovate, Lucid, or generic CSV above.")
        return
    display = trades.sort_values("exit_time", ascending=False)
    st.dataframe(
        display[["symbol", "side", "quantity", "entry_time", "exit_time", "net_pnl", "strategy", "setup", "source"]],
        hide_index=True,
        width="stretch",
        column_config={"net_pnl": st.column_config.NumberColumn("Net P&L", format="$%.2f")},
    )
    total = float(display["net_pnl"].sum())
    st.caption(f"{len(display)} trades · {money(total, signed=True)} net")
    with st.expander("Remove trade"):
        options = {
            str(row["id"]): f"{row['exit_time']} · {row['symbol']} · {money(float(row['net_pnl']), signed=True)}"
            for _, row in display.iterrows()
        }
        selected = st.selectbox("Choose trade", options, format_func=lambda value: options[value])
        if st.button("Delete trade"):
            repo.delete("trades", selected)
            st.rerun()
