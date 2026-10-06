"""Simulated time (#31): event times look like real days, but a run covers them fast.

All timestamps are timezone-aware UTC datetimes inside the generator and
ISO-8601 UTC strings ("...Z") on the wire (#33).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    """2026-09-01T13:05:07.123Z (millisecond precision)."""
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def truncate_ms(dt: datetime) -> datetime:
    """Drop sub-millisecond digits so a datetime round-trips through to_iso exactly."""
    return dt.replace(microsecond=dt.microsecond // 1000 * 1000)


@dataclass(frozen=True)
class SimClock:
    start: datetime   # first simulated moment, UTC
    days: int         # simulated history per run
    speed: float      # simulated seconds per real second

    @property
    def end(self) -> datetime:
        return self.start + timedelta(days=self.days)

    def wall_offset_s(self, sim_time: datetime) -> float:
        """Real seconds after replay start at which this simulated moment is due (used by the producer, 1.11)."""
        return (sim_time - self.start).total_seconds() / self.speed

    @classmethod
    def from_config(cls, cfg: dict) -> SimClock:
        c = cfg["clock"]
        return cls(parse_utc(c["start"]), int(c["days"]), float(c["speed"]))
