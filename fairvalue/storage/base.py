from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataRepository(ABC):
    """Storage contract shared by local CSV and a future Supabase adapter."""

    @abstractmethod
    def list(self, table: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def add(self, table: str, record: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update(self, table: str, record_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, table: str, record_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def add_many_unique(
        self, table: str, records: list[dict[str, Any]], unique_column: str
    ) -> tuple[int, int]:
        """Return (inserted_count, duplicate_count)."""
        raise NotImplementedError

