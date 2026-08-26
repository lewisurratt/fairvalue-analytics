from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from fairvalue.config import ACCOUNT_STATUSES, ACCOUNT_TYPES, LEDGER_TYPES
from fairvalue.services.privacy import anonymize_firms, shorten_ids
from fairvalue.storage.base import DataRepository
from fairvalue.ui import empty_state, money, page_header, section


ACCOUNT_GROUPINGS = {
    "Prop firm": "prop_firm",
    "Status": "status",
    "Account type": "account_type",
    "No grouping": None,
}

ACCOUNT_TABLE_COLUMNS = [
    "prop_firm",
    "account_type",
    "account_size",
    "status",
    "purchase_cost",
    "current_pnl",
    "profit_target",
    "drawdown_remaining",
]

ACCOUNT_COLUMN_CONFIG = {
    "prop_firm": "Prop firm",
    "account_type": "Type",
    "account_size": st.column_config.NumberColumn("Size", format="$%.0f"),
    "status": "Status",
    "purchase_cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
    "current_pnl": st.column_config.NumberColumn("Current P&L", format="$%.2f"),
    "profit_target": st.column_config.NumberColumn("Target", format="$%.2f"),
    "drawdown_remaining": st.column_config.NumberColumn("DD remaining", format="$%.2f"),
}


def _account_label(row: pd.Series) -> str:
    return f"{row['prop_firm']} · {row['account_type']} · {str(row['id'])[:8]}"


def _account_table(frame: pd.DataFrame, grouped_by: str | None = None) -> None:
    columns = [column for column in ACCOUNT_TABLE_COLUMNS if column != grouped_by]
    st.dataframe(
        frame[columns],
        hide_index=True,
        width="stretch",
        column_config=ACCOUNT_COLUMN_CONFIG,
    )


def _account_group_label(name: str, frame: pd.DataFrame) -> str:
    count = len(frame)
    total_size = float(frame["account_size"].sum())
    pnl = float(frame["current_pnl"].sum())
    noun = "account" if count == 1 else "accounts"
    return f"{name} · {count} {noun} · {total_size:,.0f} capital · {pnl:+,.0f} P&L"


def _grouped_account_ledger(display: pd.DataFrame, grouping_label: str) -> None:
    group_column = ACCOUNT_GROUPINGS[grouping_label]
    if group_column is None:
        _account_table(display)
        return

    groups = list(display.sort_values(group_column).groupby(group_column, sort=True, dropna=False))
    for index, (name, group) in enumerate(groups):
        display_name = str(name) if str(name).strip() else "Unassigned"
        with st.expander(_account_group_label(display_name, group), expanded=index == 0):
            summary = st.columns(5)
            summary[0].metric("Accounts", len(group))
            summary[1].metric("Combined size", f"${float(group['account_size'].sum()):,.0f}")
            summary[2].metric("Total cost", money(float(group["purchase_cost"].sum())))
            summary[3].metric("Current P&L", money(float(group["current_pnl"].sum()), signed=True))
            summary[4].metric("DD remaining", money(float(group["drawdown_remaining"].sum())))
            _account_table(group, grouped_by=group_column)


def _add_account(repo: DataRepository) -> None:
    with st.form("add_account", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        prop_firm = col1.text_input("Prop firm", placeholder="e.g. Apex Trader Funding")
        account_type = col2.selectbox("Account type", ACCOUNT_TYPES)
        status = col3.selectbox("Status", ACCOUNT_STATUSES)
        col4, col5, col6 = st.columns(3)
        account_size = col4.number_input("Account size", min_value=0.0, step=5_000.0)
        purchase_cost = col5.number_input("Purchase cost", min_value=0.0, step=10.0)
        current_pnl = col6.number_input("Current P&L", step=100.0)
        col7, col8 = st.columns(2)
        profit_target = col7.number_input("Profit target", min_value=0.0, step=100.0)
        drawdown = col8.number_input("Drawdown remaining", min_value=0.0, step=100.0)
        submitted = st.form_submit_button("Add account", type="primary", width="stretch")
        if submitted:
            if not prop_firm.strip():
                st.error("Prop firm is required.")
            else:
                repo.add(
                    "accounts",
                    {
                        "prop_firm": prop_firm.strip(),
                        "account_type": account_type,
                        "account_size": account_size,
                        "status": status,
                        "purchase_cost": purchase_cost,
                        "current_pnl": current_pnl,
                        "profit_target": profit_target,
                        "drawdown_remaining": drawdown,
                        "notes": "",
                    },
                )
                st.success("Account added.")
                st.rerun()


def _edit_account(repo: DataRepository, accounts: pd.DataFrame) -> None:
    options = {str(row["id"]): _account_label(row) for _, row in accounts.iterrows()}
    selected_id = st.selectbox("Choose account", options, format_func=lambda value: options[value])
    current = accounts.loc[accounts["id"].astype(str).eq(selected_id)].iloc[0]
    with st.form("edit_account"):
        col1, col2, col3 = st.columns(3)
        firm = col1.text_input("Prop firm", value=str(current["prop_firm"]))
        type_index = ACCOUNT_TYPES.index(current["account_type"]) if current["account_type"] in ACCOUNT_TYPES else 0
        status_index = ACCOUNT_STATUSES.index(current["status"]) if current["status"] in ACCOUNT_STATUSES else 0
        account_type = col2.selectbox("Account type", ACCOUNT_TYPES, index=type_index)
        status = col3.selectbox("Status", ACCOUNT_STATUSES, index=status_index)
        col4, col5, col6 = st.columns(3)
        size = col4.number_input("Account size", min_value=0.0, value=float(current["account_size"]), step=5_000.0)
        cost = col5.number_input("Purchase cost", min_value=0.0, value=float(current["purchase_cost"]), step=10.0)
        pnl = col6.number_input("Current P&L", value=float(current["current_pnl"]), step=100.0)
        col7, col8 = st.columns(2)
        target = col7.number_input("Profit target", min_value=0.0, value=float(current["profit_target"]), step=100.0)
        drawdown = col8.number_input("Drawdown remaining", min_value=0.0, value=float(current["drawdown_remaining"]), step=100.0)
        notes = st.text_area("Account notes", value=str(current.get("notes", "")))
        save = st.form_submit_button("Save changes", type="primary")
        if save:
            repo.update(
                "accounts",
                selected_id,
                {
                    "prop_firm": firm.strip(),
                    "account_type": account_type,
                    "status": status,
                    "account_size": size,
                    "purchase_cost": cost,
                    "current_pnl": pnl,
                    "profit_target": target,
                    "drawdown_remaining": drawdown,
                    "notes": notes.strip(),
                },
            )
            st.success("Account updated.")
            st.rerun()
    with st.expander("Danger zone"):
        confirm = st.checkbox("I understand this removes the account record", key=f"confirm_{selected_id}")
        if st.button("Delete account", disabled=not confirm):
            repo.delete("accounts", selected_id)
            st.rerun()


def _add_ledger_item(repo: DataRepository, accounts: pd.DataFrame) -> None:
    with st.form("add_ledger_item", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        item_type = col1.selectbox("Type", LEDGER_TYPES)
        item_date = col2.date_input("Date", value=date.today())
        amount = col3.number_input("Amount", min_value=0.0, step=25.0)
        account_options = {"": "Not linked"}
        account_options.update({str(row["id"]): _account_label(row) for _, row in accounts.iterrows()})
        account_id = st.selectbox("Related account", account_options, format_func=lambda value: account_options[value])
        matched = accounts.loc[accounts["id"].astype(str).eq(account_id)] if account_id else pd.DataFrame()
        default_firm = str(matched.iloc[0]["prop_firm"]) if not matched.empty else ""
        firm = st.text_input("Prop firm / vendor", value=default_firm)
        notes = st.text_area("Notes", placeholder="Payout number, platform fee, activation fee…")
        submitted = st.form_submit_button(f"Add {item_type.lower()}", type="primary", width="stretch")
        if submitted:
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                repo.add(
                    "cash_ledger",
                    {
                        "date": item_date.isoformat(),
                        "type": item_type,
                        "prop_firm": firm.strip(),
                        "account_id": account_id,
                        "amount": amount,
                        "notes": notes.strip(),
                    },
                )
                st.success(f"{item_type} added.")
                st.rerun()


def render(repo: DataRepository, demo_mode: bool) -> None:
    accounts = repo.list("accounts")
    ledger = repo.list("cash_ledger")
    page_header(
        "Capital operations",
        "Every account. One ledger.",
        "Track the cost, status, objectives, and realized cash flow of your prop-firm portfolio.",
    )
    tab_accounts, tab_ledger = st.tabs(["Accounts", "Payouts & expenses"])
    with tab_accounts:
        section("Account ledger")
        if accounts.empty:
            empty_state("No accounts yet. Add your first account below.")
        else:
            display = anonymize_firms(accounts) if demo_mode else accounts.copy()
            display = shorten_ids(display)
            grouping = st.radio(
                "Group accounts by",
                list(ACCOUNT_GROUPINGS),
                horizontal=True,
                help="Change the portfolio lens without changing the underlying account data.",
            )
            _grouped_account_ledger(display, grouping)
        with st.expander("Add account", expanded=accounts.empty):
            _add_account(repo)
        if not accounts.empty:
            with st.expander("Edit or remove account"):
                _edit_account(repo, accounts)
    with tab_ledger:
        payouts = ledger.loc[ledger["type"].str.lower().eq("payout"), "amount"].sum() if not ledger.empty else 0
        expenses = ledger.loc[ledger["type"].str.lower().eq("expense"), "amount"].sum() if not ledger.empty else 0
        a, b = st.columns(2)
        a.metric("Ledger payouts", money(float(payouts)))
        b.metric("Additional expenses", money(float(expenses)))
        if ledger.empty:
            empty_state("Record payouts and operating expenses here.")
        else:
            display_ledger = anonymize_firms(ledger) if demo_mode else ledger.copy()
            display_ledger = shorten_ids(display_ledger).sort_values("date", ascending=False)
            st.dataframe(
                display_ledger[["date", "type", "prop_firm", "amount", "notes"]],
                hide_index=True,
                width="stretch",
                column_config={"amount": st.column_config.NumberColumn("Amount", format="$%.2f")},
            )
            delete_options = {str(row["id"]): f"{row['date']} · {row['type']} · {money(float(row['amount']))}" for _, row in ledger.iterrows()}
            with st.expander("Remove ledger item"):
                selected = st.selectbox("Choose item", delete_options, format_func=lambda value: delete_options[value])
                if st.button("Delete item"):
                    repo.delete("cash_ledger", selected)
                    st.rerun()
        with st.expander("Add payout or expense", expanded=ledger.empty):
            _add_ledger_item(repo, accounts)
