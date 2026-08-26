from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import streamlit as st

from fairvalue.services.analytics import (
    behavioral_breakdown,
    behavioral_trade_context,
    daily_pnl,
    pnl_breakdown,
    trade_metrics,
)
from fairvalue.storage.base import DataRepository
from fairvalue.ui import empty_state, money, page_header, section


def _bar(frame: pd.DataFrame, x: str, title: str) -> None:
    if frame.empty:
        empty_state(f"No data available for {title.lower()}.")
        return
    frame = frame.copy()
    frame["direction"] = frame["net_pnl"].map(lambda value: "Gain" if value >= 0 else "Loss")
    chart = px.bar(
        frame,
        x=x,
        y="net_pnl",
        color="direction",
        color_discrete_map={"Gain": "#45E0A8", "Loss": "#FF6F7D"},
        hover_data=["trades"],
    )
    chart.update_layout(
        height=330,
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8EA3AF",
        xaxis=dict(title="", gridcolor="#17232D"),
        yaxis=dict(title="Net P&L", tickprefix="$", gridcolor="#17232D"),
    )
    st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})


def render(repo: DataRepository, demo_mode: bool) -> None:
    trades = repo.list("trades")
    rules = repo.list("behavior_rules")
    page_header(
        "Performance lab",
        "Find where the edge actually lives.",
        "Measure outcomes by instrument, hour, and strategy—then convert recurring patterns into operating rules.",
    )
    active_rules = rules[rules["active"].astype(str).str.lower().isin({"true", "1", "yes"})]
    if not active_rules.empty:
        rule = active_rules.iloc[0]
        st.info(f"Active guardrail — {rule['name']}: {rule['action']}")
    if trades.empty:
        empty_state("Upload trades to unlock performance analytics.")
        return
    symbols = sorted(trades["symbol"].dropna().unique())
    strategies = sorted(value for value in trades["strategy"].dropna().unique() if value)
    col1, col2 = st.columns(2)
    chosen_symbols = col1.multiselect("Symbols", symbols)
    chosen_strategies = col2.multiselect("Strategies", strategies)
    filtered = trades.copy()
    if chosen_symbols:
        filtered = filtered[filtered["symbol"].isin(chosen_symbols)]
    if chosen_strategies:
        filtered = filtered[filtered["strategy"].isin(chosen_strategies)]
    if filtered.empty:
        empty_state("No trades match these filters.")
        return

    metrics = trade_metrics(filtered)
    top = st.columns(4)
    top[0].metric("Win rate", f"{metrics.win_rate:.1f}%")
    top[1].metric("Avg winner", money(metrics.average_winner, signed=True))
    top[2].metric("Avg loser", money(metrics.average_loser, signed=True))
    pf = "∞" if math.isinf(metrics.profit_factor) else f"{metrics.profit_factor:.2f}"
    top[3].metric("Profit factor", pf)
    bottom = st.columns(4)
    bottom[0].metric("Expectancy", money(metrics.expectancy, signed=True))
    bottom[1].metric("Max drawdown", money(metrics.max_drawdown))
    bottom[2].metric("Net P&L", money(metrics.net_pnl, signed=True))
    bottom[3].metric("Trades", f"{metrics.trade_count}")

    context = behavioral_trade_context(filtered)
    section("Behavioral risk")
    st.caption("Gross P&L from execution exports; fees are only available at the report level.")
    recovery = behavioral_breakdown(context, "recovery_window")
    rapid_labels = {"≤1 min", "1–3 min", "3–5 min", "5–10 min"}
    rapid = recovery[recovery["recovery_window"].isin(rapid_labels)]
    streaks = context[context["after_two_losses"]]
    risk_cards = st.columns(4)
    risk_cards[0].metric("Trades ≤10m after loss", int(rapid["trades"].sum()))
    risk_cards[1].metric("Their gross P&L", money(rapid["gross_pnl"].sum(), signed=True))
    risk_cards[2].metric("Trades after 2 losses", len(streaks))
    risk_cards[3].metric("Their gross P&L", money(streaks["gross_pnl"].sum(), signed=True))

    behavior_col1, behavior_col2 = st.columns(2, gap="large")
    with behavior_col1:
        st.markdown("**Recovery window after a loss**")
        recovery_order = ["≤1 min", "1–3 min", "3–5 min", "5–10 min", ">10 min", "No immediate prior loss"]
        recovery["_order"] = recovery["recovery_window"].map({label: index for index, label in enumerate(recovery_order)})
        display_recovery = recovery.sort_values("_order").drop(columns="_order")
        st.dataframe(
            display_recovery.rename(
                columns={"recovery_window": "Window", "trades": "Trades", "wins": "Wins", "win_rate": "Win rate %", "gross_pnl": "Gross P&L"}
            ),
            hide_index=True,
            width="stretch",
            column_config={"Win rate %": st.column_config.NumberColumn(format="%.1f%%"), "Gross P&L": st.column_config.NumberColumn(format="$%.2f")},
        )
    with behavior_col2:
        st.markdown("**Session windows**")
        sessions = behavioral_breakdown(context, "session_window")
        st.dataframe(
            sessions.rename(
                columns={"session_window": "Window", "trades": "Trades", "wins": "Wins", "win_rate": "Win rate %", "gross_pnl": "Gross P&L"}
            ),
            hide_index=True,
            width="stretch",
            column_config={"Win rate %": st.column_config.NumberColumn(format="%.1f%%"), "Gross P&L": st.column_config.NumberColumn(format="$%.2f")},
        )

    section("Equity curve")
    daily = daily_pnl(filtered)
    curve = px.area(daily, x="date", y="cumulative_pnl", labels={"date": "", "cumulative_pnl": "Cumulative P&L"})
    curve.update_traces(line_color="#45E0A8", fillcolor="rgba(69,224,168,.10)")
    curve.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8EA3AF",
        xaxis=dict(gridcolor="#17232D"),
        yaxis=dict(gridcolor="#17232D", tickprefix="$"),
    )
    st.plotly_chart(curve, width="stretch", config={"displayModeBar": False})

    col3, col4 = st.columns(2, gap="large")
    with col3:
        section("P&L by symbol")
        _bar(pnl_breakdown(filtered, "symbol"), "symbol", "P&L by symbol")
    with col4:
        section("P&L by time of day")
        hourly = pnl_breakdown(filtered, "hour").sort_values("hour")
        _bar(hourly, "hour", "P&L by time of day")
    section("P&L by strategy")
    _bar(pnl_breakdown(filtered, "strategy"), "strategy", "P&L by strategy")
