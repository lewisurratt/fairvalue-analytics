from __future__ import annotations

import pandas as pd


def anonymize_firms(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with stable display-only aliases; source data is untouched."""
    result = frame.copy()
    if "prop_firm" not in result.columns:
        return result
    firms = sorted(name for name in result["prop_firm"].astype(str).unique() if name)
    aliases = {name: f"Prop Firm {index + 1}" for index, name in enumerate(firms)}
    result["prop_firm"] = result["prop_firm"].replace(aliases)
    return result


def shorten_ids(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("id", "account_id"):
        if column in result.columns:
            result[column] = result[column].astype(str).map(lambda value: value[:8] if value else "")
    return result

