import pandas as pd

from fairvalue.services.analytics import (
    behavioral_breakdown,
    behavioral_trade_context,
    cash_metrics,
    reported_daily_pnl,
    trade_metrics,
)


def test_cash_metrics_include_account_costs_and_extra_expenses():
    accounts = pd.DataFrame(
        [
            {"purchase_cost": 100, "status": "Funded"},
            {"purchase_cost": 50, "status": "Breached"},
        ]
    )
    ledger = pd.DataFrame(
        [
            {"type": "Payout", "amount": 500},
            {"type": "Expense", "amount": 25},
        ]
    )
    result = cash_metrics(accounts, ledger)
    assert result.total_spend == 175
    assert result.total_payouts == 500
    assert result.net_realized_profit == 325
    assert result.active_accounts == 1


def test_trade_metrics_and_peak_to_trough_drawdown():
    trades = pd.DataFrame(
        [
            {"exit_time": "2026-01-01 10:00", "net_pnl": 100},
            {"exit_time": "2026-01-02 10:00", "net_pnl": -40},
            {"exit_time": "2026-01-03 10:00", "net_pnl": -90},
            {"exit_time": "2026-01-04 10:00", "net_pnl": 60},
        ]
    )
    result = trade_metrics(trades)
    assert result.trade_count == 4
    assert result.win_rate == 50
    assert result.average_winner == 80
    assert result.average_loser == -65
    assert result.max_drawdown == 130


def test_reported_daily_pnl_avoids_overlapping_intraday_snapshot():
    reports = pd.DataFrame(
        [
            {"date": "2026-08-10", "net_pnl": -235, "include_in_daily_total": "false"},
            {"date": "2026-08-10", "net_pnl": 140.4, "include_in_daily_total": "true"},
            {"date": "2026-08-11", "net_pnl": -251.7, "include_in_daily_total": "true"},
        ]
    )
    result = reported_daily_pnl(reports)
    assert list(result["net_pnl"]) == [140.4, -251.7]
    assert round(result.iloc[-1]["cumulative_pnl"], 2) == -111.3


def test_behavioral_context_isolated_by_account_and_tags_loss_streaks():
    trades = pd.DataFrame(
        [
            {"id": "a1", "account_id": "a", "source": "x", "symbol": "MNQ", "entry_time": "2026-08-26 09:30", "exit_time": "2026-08-26 09:31", "gross_pnl": -100},
            {"id": "b1", "account_id": "b", "source": "x", "symbol": "MGC", "entry_time": "2026-08-26 09:32", "exit_time": "2026-08-26 09:33", "gross_pnl": 50},
            {"id": "a2", "account_id": "a", "source": "x", "symbol": "MNQ", "entry_time": "2026-08-26 09:33", "exit_time": "2026-08-26 09:34", "gross_pnl": -75},
            {"id": "a3", "account_id": "a", "source": "x", "symbol": "MNQ", "entry_time": "2026-08-26 09:36", "exit_time": "2026-08-26 09:37", "gross_pnl": -455},
        ]
    )
    context = behavioral_trade_context(trades)
    a2 = context.loc[context["id"].eq("a2")].iloc[0]
    a3 = context.loc[context["id"].eq("a3")].iloc[0]
    b1 = context.loc[context["id"].eq("b1")].iloc[0]
    assert a2["recovery_window"] == "1–3 min"
    assert bool(a3["after_two_losses"])
    assert b1["recovery_window"] == "No immediate prior loss"
    recovery = behavioral_breakdown(context, "recovery_window")
    assert int(recovery["trades"].sum()) == 4
