from io import StringIO

from fairvalue.services.importer import normalize_trade_csv


def test_completed_trade_normalization_is_deterministic():
    csv = StringIO(
        "Symbol,Side,Quantity,Entry Time,Exit Time,Entry Price,Exit Price,Gross PnL,Fees\n"
        "NQ,Long,1,2026-08-01 09:40,2026-08-01 09:50,23000,23010,200,4.2\n"
    )
    first = normalize_trade_csv(csv, "Tradovate", "acc-1")[0]
    csv.seek(0)
    second = normalize_trade_csv(csv, "Tradovate", "acc-1")[0]
    assert first["net_pnl"] == 195.8
    assert first["trade_key"] == second["trade_key"]


def test_fill_rows_are_collapsed_when_position_flattens():
    csv = StringIO(
        "Timestamp,Symbol,Action,Qty,Price,Commission\n"
        "2026-08-01 09:40,MNQ,Buy,2,100,2\n"
        "2026-08-01 09:42,MNQ,Buy,1,102,1\n"
        "2026-08-01 09:50,MNQ,Sell,3,110,3\n"
    )
    records = normalize_trade_csv(csv, "Generic CSV", "acc-1")
    assert len(records) == 1
    assert records[0]["quantity"] == 3
    assert round(records[0]["gross_pnl"], 2) == 28
    assert round(records[0]["net_pnl"], 2) == 22


def test_tradovate_partial_rows_collapse_and_infer_short_direction():
    csv = StringIO(
        "symbol,buyFillId,sellFillId,qty,buyPrice,sellPrice,pnl,boughtTimestamp,soldTimestamp\n"
        "MGCZ6,320,314,1,4086.1,4083.7,$(24.00),07/31/2026 09:41:13,07/31/2026 09:40:03\n"
        "MGCZ6,325,314,4,4086.3,4083.7,$(104.00),07/31/2026 09:41:13,07/31/2026 09:40:03\n"
    )
    records = normalize_trade_csv(csv, "Tradovate", "acc-1")
    assert len(records) == 1
    assert records[0]["side"] == "Short"
    assert records[0]["quantity"] == 5
    assert records[0]["gross_pnl"] == -128
    assert records[0]["entry_price"] == 4083.7
    assert round(records[0]["exit_price"], 2) == 4086.26
