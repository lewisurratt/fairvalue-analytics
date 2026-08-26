from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CashMetrics:
    total_spend: float
    total_payouts: float
    net_realized_profit: float
    roi: float
    active_accounts: int


@dataclass(frozen=True)
class TradeMetrics:
    trade_count: int
    win_rate: float
    average_winner: float
    average_loser: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    net_pnl: float


def cash_metrics(accounts: pd.DataFrame, ledger: pd.DataFrame) -> CashMetrics:
    account_costs = pd.to_numeric(accounts.get("purchase_cost", pd.Series(dtype=float)), errors="coerce").sum()
    amounts = pd.to_numeric(ledger.get("amount", pd.Series(dtype=float)), errors="coerce").fillna(0)
    types = ledger.get("type", pd.Series(index=ledger.index, dtype=str)).astype(str).str.lower()
    expenses = amounts[types.eq("expense")].sum()
    payouts = amounts[types.eq("payout")].sum()
    spend = float(account_costs + expenses)
    net = float(payouts - spend)
    roi = (net / spend * 100.0) if spend else 0.0
    statuses = accounts.get("status", pd.Series(index=accounts.index, dtype=str)).astype(str).str.lower()
    active = int(statuses.isin({"eval", "funded", "passed"}).sum())
    return CashMetrics(spend, float(payouts), net, roi, active)


def trade_metrics(trades: pd.DataFrame) -> TradeMetrics:
    if trades.empty:
        return TradeMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    ordered = trades.copy()
    ordered["net_pnl"] = pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0)
    ordered["exit_time"] = pd.to_datetime(ordered["exit_time"], errors="coerce")
    ordered = ordered.sort_values("exit_time", na_position="last")
    pnl = ordered["net_pnl"]
    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]
    gross_profit = float(winners.sum())
    gross_loss = float(abs(losers.sum()))
    profit_factor = gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0.0)
    cumulative = pnl.cumsum()
    running_peak = cumulative.cummax().clip(lower=0)
    max_drawdown = float(abs((cumulative - running_peak).min()))
    return TradeMetrics(
        trade_count=len(pnl),
        win_rate=float((pnl > 0).mean() * 100.0),
        average_winner=float(winners.mean()) if not winners.empty else 0.0,
        average_loser=float(losers.mean()) if not losers.empty else 0.0,
        profit_factor=float(profit_factor),
        expectancy=float(pnl.mean()),
        max_drawdown=max_drawdown,
        net_pnl=float(pnl.sum()),
    )


def daily_pnl(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["date", "net_pnl", "cumulative_pnl"])
    frame = trades.copy()
    frame["date"] = pd.to_datetime(frame["exit_time"], errors="coerce").dt.date
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    result = frame.dropna(subset=["date"]).groupby("date", as_index=False)["net_pnl"].sum()
    result = result.sort_values("date")
    result["cumulative_pnl"] = result["net_pnl"].cumsum()
    return result


def reported_daily_pnl(reports: pd.DataFrame) -> pd.DataFrame:
    """Aggregate audited report totals without fabricating individual trades."""
    if reports.empty:
        return pd.DataFrame(columns=["date", "net_pnl", "cumulative_pnl"])
    frame = reports.copy()
    include = frame["include_in_daily_total"].astype(str).str.lower().isin({"true", "1", "yes"})
    frame = frame.loc[include]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    result = frame.dropna(subset=["date"]).groupby("date", as_index=False)["net_pnl"].sum()
    result = result.sort_values("date")
    result["cumulative_pnl"] = result["net_pnl"].cumsum()
    return result


def pnl_breakdown(trades: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=[dimension, "net_pnl", "trades"])
    frame = trades.copy()
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    if dimension == "hour":
        times = pd.to_datetime(frame["exit_time"], errors="coerce")
        frame[dimension] = times.dt.strftime("%H:00")
    elif dimension not in frame.columns:
        raise ValueError(f"Unknown breakdown dimension: {dimension}")
    frame[dimension] = frame[dimension].replace("", "Untagged").fillna("Unknown")
    return (
        frame.groupby(dimension, as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), trades=("id", "count"))
        .sort_values("net_pnl", ascending=False)
    )


def behavioral_trade_context(trades: pd.DataFrame) -> pd.DataFrame:
    """Tag each trade with the immediately preceding loss context.

    Streams are isolated by account (or source when an account ID is absent), so
    activity in one account never creates a false loss streak in another.
    Execution exports do not contain fee allocation, so these diagnostics use
    gross P&L and label it explicitly in the UI.
    """
    columns = [
        "id",
        "account_id",
        "source",
        "symbol",
        "entry_time",
        "exit_time",
        "gross_pnl",
        "recovery_window",
        "after_two_losses",
        "session_window",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)

    frame = trades.copy()
    for column in ("id", "account_id", "source", "symbol"):
        if column not in frame:
            frame[column] = ""
    frame["gross_pnl"] = pd.to_numeric(frame.get("gross_pnl", 0), errors="coerce").fillna(0.0)
    frame["entry_time"] = pd.to_datetime(frame.get("entry_time"), errors="coerce")
    frame["exit_time"] = pd.to_datetime(frame.get("exit_time"), errors="coerce")
    account = frame["account_id"].fillna("").astype(str).str.strip()
    source = frame["source"].fillna("").astype(str).str.strip()
    frame["_stream"] = account.where(account.ne(""), source.where(source.ne(""), "Unassigned"))
    frame = frame.sort_values(["_stream", "entry_time", "exit_time"], na_position="last").reset_index(drop=True)

    previous_pnl = frame.groupby("_stream", sort=False)["gross_pnl"].shift(1)
    previous_two_pnl = frame.groupby("_stream", sort=False)["gross_pnl"].shift(2)
    previous_exit = frame.groupby("_stream", sort=False)["exit_time"].shift(1)
    minutes_after = (frame["entry_time"] - previous_exit).dt.total_seconds().div(60)
    immediately_after_loss = previous_pnl.lt(0)

    frame["recovery_window"] = "No immediate prior loss"
    valid = immediately_after_loss & minutes_after.notna()
    frame.loc[valid & minutes_after.le(1), "recovery_window"] = "≤1 min"
    frame.loc[valid & minutes_after.gt(1) & minutes_after.le(3), "recovery_window"] = "1–3 min"
    frame.loc[valid & minutes_after.gt(3) & minutes_after.le(5), "recovery_window"] = "3–5 min"
    frame.loc[valid & minutes_after.gt(5) & minutes_after.le(10), "recovery_window"] = "5–10 min"
    frame.loc[valid & minutes_after.gt(10), "recovery_window"] = ">10 min"
    frame["after_two_losses"] = immediately_after_loss & previous_two_pnl.lt(0)

    minutes = frame["entry_time"].dt.hour.mul(60).add(frame["entry_time"].dt.minute)
    frame["session_window"] = "Other"
    frame.loc[minutes.ge(9 * 60 + 30) & minutes.lt(9 * 60 + 40), "session_window"] = "09:30–09:40"
    frame.loc[minutes.ge(9 * 60 + 40) & minutes.lt(10 * 60 + 30), "session_window"] = "09:40–10:30"
    frame.loc[minutes.ge(14 * 60) & minutes.lt(15 * 60), "session_window"] = "14:00–15:00"
    return frame[columns]


def behavioral_breakdown(context: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if context.empty:
        return pd.DataFrame(columns=[dimension, "trades", "wins", "win_rate", "gross_pnl"])
    if dimension not in {"recovery_window", "session_window", "after_two_losses"}:
        raise ValueError(f"Unknown behavioral dimension: {dimension}")
    frame = context.copy()
    if dimension == "after_two_losses":
        frame[dimension] = frame[dimension].map({True: "After 2 losses", False: "Other trades"})
    grouped = (
        frame.groupby(dimension, as_index=False, dropna=False)
        .agg(
            trades=("id", "count"),
            wins=("gross_pnl", lambda values: int((values > 0).sum())),
            gross_pnl=("gross_pnl", "sum"),
        )
    )
    grouped["win_rate"] = grouped["wins"].div(grouped["trades"]).mul(100.0)
    return grouped
