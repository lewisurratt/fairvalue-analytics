from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from fairvalue.schema import NUMERIC_COLUMNS, TABLE_SCHEMAS
from fairvalue.storage.base import DataRepository


class CsvRepository(DataRepository):
    """Small local repository with stable, relational-style table schemas.

    The UI and analytics depend on DataRepository, not CSV details. A Supabase
    implementation can therefore replace this class without changing the views.
    """

    _lock = threading.RLock()

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _path(self, table: str) -> Path:
        if table not in TABLE_SCHEMAS:
            raise ValueError(f"Unknown table: {table}")
        return self.data_dir / f"{table}.csv"

    def _ensure_tables(self) -> None:
        for table, columns in TABLE_SCHEMAS.items():
            path = self._path(table)
            if not path.exists():
                pd.DataFrame(columns=columns).to_csv(path, index=False)

    def list(self, table: str) -> pd.DataFrame:
        with self._lock:
            frame = pd.read_csv(self._path(table), dtype=str, keep_default_na=False)
        frame = frame.reindex(columns=TABLE_SCHEMAS[table], fill_value="")
        for column in NUMERIC_COLUMNS.get(table, []):
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
        return frame

    def _write(self, table: str, frame: pd.DataFrame) -> None:
        path = self._path(table)
        temp_path = path.with_suffix(".tmp")
        normalized = frame.reindex(columns=TABLE_SCHEMAS[table], fill_value="")
        normalized.to_csv(temp_path, index=False)
        os.replace(temp_path, path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_record(self, table: str, record: dict[str, Any]) -> dict[str, Any]:
        unknown = set(record) - set(TABLE_SCHEMAS[table])
        if unknown:
            raise ValueError(f"Unknown {table} fields: {', '.join(sorted(unknown))}")
        result = {column: record.get(column, "") for column in TABLE_SCHEMAS[table]}
        result["id"] = str(result.get("id") or uuid.uuid4())
        now = self._now()
        if "created_at" in result and not result["created_at"]:
            result["created_at"] = now
        if "updated_at" in result:
            result["updated_at"] = now
        if "imported_at" in result and not result["imported_at"]:
            result["imported_at"] = now
        return result

    def add(self, table: str, record: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_record(table, record)
        with self._lock:
            frame = self.list(table)
            frame = pd.concat([frame, pd.DataFrame([normalized])], ignore_index=True)
            self._write(table, frame)
        return normalized

    def update(self, table: str, record_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        if "id" in changes:
            raise ValueError("Record IDs cannot be changed")
        unknown = set(changes) - set(TABLE_SCHEMAS[table])
        if unknown:
            raise ValueError(f"Unknown {table} fields: {', '.join(sorted(unknown))}")
        with self._lock:
            frame = self.list(table)
            matches = frame.index[frame["id"].astype(str) == str(record_id)].tolist()
            if not matches:
                raise KeyError(f"No {table} record with id {record_id}")
            index = matches[0]
            for key, value in changes.items():
                frame.at[index, key] = value
            if "updated_at" in frame.columns:
                frame.at[index, "updated_at"] = self._now()
            self._write(table, frame)
            result = frame.loc[index].to_dict()
        return result

    def delete(self, table: str, record_id: str) -> bool:
        with self._lock:
            frame = self.list(table)
            keep = frame["id"].astype(str) != str(record_id)
            removed = int((~keep).sum())
            if removed:
                self._write(table, frame.loc[keep].reset_index(drop=True))
        return bool(removed)

    def add_many_unique(
        self, table: str, records: list[dict[str, Any]], unique_column: str
    ) -> tuple[int, int]:
        if unique_column not in TABLE_SCHEMAS[table]:
            raise ValueError(f"Unknown unique column: {unique_column}")
        if not records:
            return 0, 0
        with self._lock:
            frame = self.list(table)
            existing = set(frame[unique_column].astype(str))
            accepted: list[dict[str, Any]] = []
            duplicates = 0
            for record in records:
                normalized = self._normalize_record(table, record)
                key = str(normalized[unique_column])
                if not key or key in existing:
                    duplicates += 1
                    continue
                existing.add(key)
                accepted.append(normalized)
            if accepted:
                frame = pd.concat([frame, pd.DataFrame(accepted)], ignore_index=True)
                self._write(table, frame)
        return len(accepted), duplicates

