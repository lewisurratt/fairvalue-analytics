from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import BinaryIO, TextIO

import pandas as pd


ALIASES: dict[str, list[str]] = {
    "symbol": ["symbol", "contract", "instrument", "product"],
    "side": ["side", "action", "buysell", "buy_sell", "direction"],
    "quantity": ["quantity", "qty", "filledqty", "filled_qty", "size"],
    "entry_time": ["entrytime", "entry_time", "opentime", "open_time", "boughttimestamp"],
    "exit_time": ["exittime", "exit_time", "closetime", "close_time", "soldtimestamp", "timestamp"],
    "timestamp": ["timestamp", "time", "datetime", "filltime", "filledtime"],
    "entry_price": ["entryprice", "entry_price", "openprice", "open_price", "buyprice"],
    "exit_price": ["exitprice", "exit_price", "closeprice", "close_price", "sellprice", "price"],
    "price": ["price", "fillprice", "filledprice", "avgprice"],
    "gross_pnl": ["grosspnl", "gross_pnl", "pnl", "pl", "realizedpnl", "realized_pnl"],
    "net_pnl": ["netpnl", "net_pnl", "netpl", "net_pl"],
    "fees": ["fees", "fee", "commission", "commissions"],
    "strategy": ["strategy", "strategytag", "strategy_tag"],
    "setup": ["setup", "setuptag", "setup_tag"],
    "account_id": ["accountid", "account_id", "account", "accountname"],
    "trade_id": ["tradeid", "trade_id", "positionid", "position_id", "orderid"],
    "notes": ["notes", "note", "comment"],
}


def _clean_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _column_map(frame: pd.DataFrame) -> dict[str, str]:
    cleaned = {_clean_name(column): column for column in frame.columns}
    found: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            key = _clean_name(alias)
            if key in cleaned:
                found[target] = cleaned[key]
                break
    return found


def _value(row: pd.Series, columns: dict[str, str], name: str, default: object = "") -> object:
    column = columns.get(name)
    if not column:
        return default
    value = row.get(column, default)
    return default if pd.isna(value) else value


def _number(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    cleaned = re.sub(r"[^0-9.\-()]", "", str(value))
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return default


def _timestamp(value: object) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.isoformat()


def _direction(value: object) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"buy", "b", "long", "bot"} or "buy" in normalized:
        return "Long"
    if normalized in {"sell", "s", "short", "sld"} or "sell" in normalized:
        return "Short"
    return str(value).title() or "Unknown"


def _session(timestamp: str) -> str:
    parsed = pd.to_datetime(timestamp, errors="coerce")
    if pd.isna(parsed):
        return "Other"
    hour = parsed.hour
    if 9 <= hour < 12:
        return "New York AM"
    if 12 <= hour < 16:
        return "New York PM"
    if 2 <= hour < 9:
        return "London"
    return "Other"


def _trade_key(record: dict[str, object]) -> str:
    parts = [
        record.get("source", ""),
        record.get("account_id", ""),
        record.get("symbol", ""),
        record.get("side", ""),
        record.get("quantity", ""),
        record.get("entry_time", ""),
        record.get("exit_time", ""),
        record.get("entry_price", ""),
        record.get("exit_price", ""),
        record.get("net_pnl", ""),
    ]
    payload = "|".join(str(value).strip().lower() for value in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _base_record(source: str, account_id: str) -> dict[str, object]:
    return {
        "source": source,
        "account_id": account_id,
        "strategy": "",
        "setup": "",
        "notes": "",
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


def _collapse_linked_execution_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Collapse Tradovate partial-fill rows that share a buy or sell fill ID."""
    raw_columns = {_clean_name(column): column for column in frame.columns}
    buy_id = raw_columns.get("buyfillid")
    sell_id = raw_columns.get("sellfillid")
    quantity = raw_columns.get("qty") or raw_columns.get("quantity")
    if not buy_id or not sell_id or not quantity:
        return frame

    fill_values = pd.concat([frame[buy_id], frame[sell_id]], ignore_index=True).astype(str)
    frequencies = fill_values.value_counts().to_dict()
    group_keys: list[str] = []
    for index, row in frame.iterrows():
        candidates = [str(row[buy_id]), str(row[sell_id])]
        repeated = [value for value in candidates if value and frequencies.get(value, 0) > 1]
        if repeated:
            chosen = max(repeated, key=lambda value: frequencies[value])
            group_keys.append(f"fill:{chosen}")
        else:
            group_keys.append(f"row:{index}")

    working = frame.copy()
    working["__group_key"] = group_keys
    collapsed: list[pd.Series] = []
    buy_price = raw_columns.get("buyprice")
    sell_price = raw_columns.get("sellprice")
    pnl_column = next(
        (raw_columns[name] for name in ("netpnl", "grosspnl", "pnl", "pl") if name in raw_columns),
        None,
    )
    bought_time = raw_columns.get("boughttimestamp")
    sold_time = raw_columns.get("soldtimestamp")

    for _, group in working.groupby("__group_key", sort=False):
        if len(group) == 1:
            collapsed.append(group.iloc[0].drop(labels="__group_key"))
            continue
        record = group.iloc[0].drop(labels="__group_key").copy()
        weights = group[quantity].map(_number).abs()
        total_quantity = float(weights.sum())
        record[quantity] = total_quantity
        for price_column in (buy_price, sell_price):
            if price_column:
                prices = group[price_column].map(_number)
                record[price_column] = float((prices * weights).sum() / total_quantity) if total_quantity else 0.0
        if pnl_column:
            record[pnl_column] = float(group[pnl_column].map(_number).sum())
        if bought_time and sold_time:
            buys = pd.to_datetime(group[bought_time], errors="coerce").dropna()
            sells = pd.to_datetime(group[sold_time], errors="coerce").dropna()
            if not buys.empty and not sells.empty:
                if buys.min() <= sells.min():
                    record[bought_time] = buys.min().isoformat()
                    record[sold_time] = sells.max().isoformat()
                else:
                    record[sold_time] = sells.min().isoformat()
                    record[bought_time] = buys.max().isoformat()
        collapsed.append(record)
    return pd.DataFrame(collapsed).reset_index(drop=True)


def _normalize_completed_rows(
    frame: pd.DataFrame, columns: dict[str, str], source: str, default_account_id: str
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        record = _base_record(source, str(_value(row, columns, "account_id", default_account_id)))
        gross = _number(_value(row, columns, "gross_pnl"))
        fees = abs(_number(_value(row, columns, "fees")))
        net_value = _value(row, columns, "net_pnl", None)
        entry_time = _timestamp(_value(row, columns, "entry_time"))
        exit_time = _timestamp(_value(row, columns, "exit_time"))
        side = _direction(_value(row, columns, "side"))
        entry_price = _number(_value(row, columns, "entry_price"))
        exit_price = _number(_value(row, columns, "exit_price"))
        is_buy_sell_export = (
            _clean_name(columns.get("entry_time", "")) == "boughttimestamp"
            and _clean_name(columns.get("exit_time", "")) == "soldtimestamp"
        )
        if side == "Unknown" and is_buy_sell_export and entry_time and exit_time:
            buy_time = pd.to_datetime(entry_time, errors="coerce")
            sell_time = pd.to_datetime(exit_time, errors="coerce")
            if not pd.isna(buy_time) and not pd.isna(sell_time):
                if buy_time <= sell_time:
                    side = "Long"
                else:
                    side = "Short"
                    entry_time, exit_time = exit_time, entry_time
                    entry_price, exit_price = exit_price, entry_price
        record.update(
            {
                "symbol": str(_value(row, columns, "symbol", "Unknown")).upper(),
                "side": side,
                "quantity": abs(_number(_value(row, columns, "quantity", 1), 1)),
                "entry_time": entry_time or exit_time,
                "exit_time": exit_time or entry_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_pnl": gross,
                "fees": fees,
                "net_pnl": _number(net_value, gross - fees) if net_value not in (None, "") else gross - fees,
                "strategy": str(_value(row, columns, "strategy")),
                "setup": str(_value(row, columns, "setup")),
                "session": _session(exit_time or entry_time),
                "notes": str(_value(row, columns, "notes")),
            }
        )
        record["trade_key"] = _trade_key(record)
        records.append(record)
    return records


def _normalize_fill_rows(
    frame: pd.DataFrame, columns: dict[str, str], source: str, default_account_id: str
) -> list[dict[str, object]]:
    timestamp_column = columns.get("timestamp") or columns.get("exit_time")
    if not timestamp_column or "side" not in columns or "price" not in columns and "exit_price" not in columns:
        raise ValueError("Fill data needs timestamp, side/action, price, quantity, and symbol columns.")
    ordered = frame.copy()
    ordered["__time"] = pd.to_datetime(ordered[timestamp_column], errors="coerce")
    ordered = ordered.sort_values("__time")
    states: dict[tuple[str, str], dict[str, object]] = {}
    records: list[dict[str, object]] = []
    for _, row in ordered.iterrows():
        symbol = str(_value(row, columns, "symbol", "Unknown")).upper()
        account_id = str(_value(row, columns, "account_id", default_account_id))
        key = (account_id, symbol)
        direction = _direction(_value(row, columns, "side"))
        signed_qty = abs(_number(_value(row, columns, "quantity", 1), 1)) * (1 if direction == "Long" else -1)
        price = _number(_value(row, columns, "price", _value(row, columns, "exit_price")))
        when = _timestamp(row["__time"])
        fee = abs(_number(_value(row, columns, "fees")))
        state = states.get(key)
        if not state or float(state["position"]) == 0:
            states[key] = {
                "position": signed_qty,
                "entry_price": price,
                "entry_time": when,
                "closed_qty": 0.0,
                "gross_pnl": 0.0,
                "fees": fee,
                "side": "Long" if signed_qty > 0 else "Short",
            }
            continue
        position = float(state["position"])
        if position * signed_qty > 0:
            new_position = position + signed_qty
            state["entry_price"] = (
                abs(position) * float(state["entry_price"]) + abs(signed_qty) * price
            ) / abs(new_position)
            state["position"] = new_position
            state["fees"] = float(state["fees"]) + fee
            continue
        closing_qty = min(abs(position), abs(signed_qty))
        multiplier = 1 if position > 0 else -1
        state["gross_pnl"] = float(state["gross_pnl"]) + (price - float(state["entry_price"])) * closing_qty * multiplier
        state["closed_qty"] = float(state["closed_qty"]) + closing_qty
        state["fees"] = float(state["fees"]) + fee
        remaining = position + signed_qty
        if abs(remaining) < 1e-9 or position * remaining < 0:
            record = _base_record(source, account_id)
            gross = float(state["gross_pnl"])
            fees = float(state["fees"])
            record.update(
                {
                    "symbol": symbol,
                    "side": state["side"],
                    "quantity": float(state["closed_qty"]),
                    "entry_time": state["entry_time"],
                    "exit_time": when,
                    "entry_price": float(state["entry_price"]),
                    "exit_price": price,
                    "gross_pnl": gross,
                    "fees": fees,
                    "net_pnl": gross - fees,
                    "session": _session(when),
                }
            )
            record["trade_key"] = _trade_key(record)
            records.append(record)
        if abs(remaining) < 1e-9:
            states.pop(key, None)
        elif position * remaining < 0:
            states[key] = {
                "position": remaining,
                "entry_price": price,
                "entry_time": when,
                "closed_qty": 0.0,
                "gross_pnl": 0.0,
                "fees": 0.0,
                "side": "Long" if remaining > 0 else "Short",
            }
        else:
            state["position"] = remaining
    return records


def normalize_trade_csv(
    file: BinaryIO | TextIO | BytesIO | StringIO,
    source: str,
    default_account_id: str = "",
) -> list[dict[str, object]]:
    """Normalize completed-trade exports or raw fills into the trades schema."""
    frame = pd.read_csv(file)
    if frame.empty:
        return []
    frame = _collapse_linked_execution_rows(frame)
    columns = _column_map(frame)
    if "symbol" not in columns:
        raise ValueError("No symbol/contract column was found in this CSV.")
    completed = "gross_pnl" in columns or "net_pnl" in columns or (
        "entry_price" in columns and "exit_price" in columns and "entry_time" in columns
    )
    if completed:
        return _normalize_completed_rows(frame, columns, source, default_account_id)
    return _normalize_fill_rows(frame, columns, source, default_account_id)
