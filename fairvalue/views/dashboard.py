from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from fairvalue.services.analytics import cash_metrics, daily_pnl, reported_daily_pnl
from fairvalue.services.privacy import anonymize_firms
from fairvalue.storage.base import DataRepository
from fairvalue.ui import empty_state, money, page_header, safe, section, tags


def render(repo: DataRepository, demo_mode: bool) -> None:
    accounts = repo.list("accounts")
    ledger = repo.list("cash_ledger")
    journals = repo.list("journals")
    trades = repo.list("trades")
    reports = repo.list("daily_performance")
    display_accounts = anonymize_firms(accounts) if demo_mode else accounts
    metrics = cash_metrics(accounts, ledger)

    page_header(
        "Portfolio command center",
        "Know the numbers. Keep the lesson.",
        "A clear view of prop-firm capital, realized cash performance, and the decisions shaping your edge.",
    )
    if demo_mode:
        st.info(
            "This public portfolio view uses synthetic records to demonstrate the analysis "
            "without exposing personal accounts or performance."
        )

    columns = st.columns(5)
    columns[0].metric("Total spend", f"${metrics.total_spend:,.0f}")
    columns[1].metric("Total payouts", f"${metrics.total_payouts:,.0f}")
    net_prefix = "+" if metrics.net_realized_profit > 0 else "-" if metrics.net_realized_profit < 0 else ""
    columns[2].metric("Net realized", f"{net_prefix}${abs(metrics.net_realized_profit):,.0f}")
    columns[3].metric("Cash ROI", f"{metrics.roi:,.1f}%")
    columns[4].metric("Active accounts", f"{metrics.active_accounts}")

    left, right = st.columns([1.7, 1], gap="large")
    with left:
        section("Daily trading P&L")
        daily = reported_daily_pnl(reports) if not reports.empty else daily_pnl(trades)
        if daily.empty:
            empty_state("Upload trades to unlock the daily performance curve.")
        else:
            daily["direction"] = daily["net_pnl"].map(lambda value: "Gain" if value >= 0 else "Loss")
            chart = px.bar(
                daily,
                x="date",
                y="net_pnl",
                color="direction",
                color_discrete_map={"Gain": "#45E0A8", "Loss": "#FF6F7D"},
                labels={"date": "", "net_pnl": "Net P&L"},
            )
            chart.update_layout(
                height=350,
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#8EA3AF",
                xaxis=dict(gridcolor="#17232D"),
                yaxis=dict(gridcolor="#17232D", tickprefix="$"),
            )
            st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
    with right:
        section("Account health")
        if display_accounts.empty:
            empty_state("Add an account to start tracking your prop-firm portfolio.")
        else:
            health = display_accounts.copy()
            health["current_pnl"] = pd.to_numeric(health["current_pnl"], errors="coerce").fillna(0)
            health["drawdown_remaining"] = pd.to_numeric(health["drawdown_remaining"], errors="coerce").fillna(0)
            for _, account in health.head(5).iterrows():
                pnl_class = "fv-positive" if account["current_pnl"] >= 0 else "fv-negative"
                st.markdown(
                    f'<div class="fv-card"><div class="fv-card-top">'
                    f'<div><div class="fv-card-title">{safe(account["prop_firm"])}</div>'
                    f'<div class="fv-card-meta">{safe(account["account_type"])} · {safe(account["status"])}</div></div>'
                    f'<div class="{pnl_class}">{money(account["current_pnl"], signed=True)}</div></div>'
                    f'<div class="fv-card-meta" style="margin-top:.7rem">Drawdown remaining · {money(account["drawdown_remaining"])}</div></div>',
                    unsafe_allow_html=True,
                )

    section("Recent journal entries")
    if journals.empty:
        empty_state("Your newest lessons will appear here after you add a journal entry.")
        return
    recent = journals.sort_values(["date", "created_at"], ascending=False).head(4)
    for _, entry in recent.iterrows():
        pnl = float(entry["pnl"])
        pnl_class = "fv-positive" if pnl >= 0 else "fv-negative"
        lesson = entry["main_lesson"] or entry["what_happened"]
        st.markdown(
            f'<div class="fv-card"><div class="fv-card-top"><div>'
            f'<div class="fv-card-title">{safe(entry["date"])} · {safe(entry["session"])}</div>'
            f'<div class="fv-card-meta">Trading debrief</div></div><div class="{pnl_class}">{money(pnl, signed=True)}</div></div>'
            f'<div class="fv-card-copy">{safe(lesson)}</div>{tags(entry["strategy_tags"])}{tags(entry["setup_tags"])}</div>',
            unsafe_allow_html=True,
        )
