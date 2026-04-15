"""Re-export for compatibility; ingestion pipeline lives in `app.fetcher`."""

from app.fetcher import upsert_job

__all__ = ["upsert_job"]
