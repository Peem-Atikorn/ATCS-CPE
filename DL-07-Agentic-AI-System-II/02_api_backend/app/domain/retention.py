"""Retention periods (docs/03_data_design.md section 6)."""

from __future__ import annotations

from datetime import datetime, timedelta


def expires_at(start: datetime, days: int) -> datetime:
    if days <= 0:
        raise ValueError("retention days must be positive")
    return start + timedelta(days=days)
