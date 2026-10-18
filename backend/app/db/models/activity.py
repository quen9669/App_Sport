"""Training activities (runs, rides, gym sessions...) and their time series."""

from datetime import datetime

from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class Activity(Base):
    """One activity, normalised from its source.

    Units are SI everywhere (seconds, metres, metres per second) so that
    calculations never have to guess; conversion to km, min/km or km/h is done
    for display only.
    """

    __tablename__ = "activity"
    # The rule that makes imports idempotent: one row per (source, external id).
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255), default="")
    # Raw sport type from the source (Strava "Run", "Ride", "WeightTraining", "Workout"...).
    # Phase 2 maps it to "strength" / "cardio", with manual correction.
    sport_type: Mapped[str] = mapped_column(String(64), index=True)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    # IANA timezone of the place where the activity happened, e.g. "Europe/Luxembourg".
    timezone: Mapped[str | None] = mapped_column(String(64))
    elapsed_time_s: Mapped[int] = mapped_column(Integer)
    moving_time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    average_speed_mps: Mapped[float | None] = mapped_column(Float)
    max_speed_mps: Mapped[float | None] = mapped_column(Float)
    average_heartrate: Mapped[float | None] = mapped_column(Float)
    max_heartrate: Mapped[float | None] = mapped_column(Float)
    average_cadence: Mapped[float | None] = mapped_column(Float)
    # Google "encoded polyline" of the route, already simplified by Strava. Enough for the map.
    summary_polyline: Mapped[str | None] = mapped_column(Text)
    has_heartrate: Mapped[bool] = mapped_column(default=False)
    is_manual: Mapped[bool] = mapped_column(default=False)
    is_trainer: Mapped[bool] = mapped_column(default=False)  # indoor (home trainer, treadmill)
    # Manual correction of the automatic strength/cardio/other category (None = automatic).
    # Syncs never touch this column, so a correction survives every re-sync.
    category_override: Mapped[str | None] = mapped_column(String(16))
    # Id of the same activity in Garmin Connect. For Garmin rows it equals
    # ``external_id``; for Strava rows it is read from Strava's ``external_id``
    # ("garmin_ping_123...") when the activity came from the watch. It is the
    # surest way to recognise the same session in both sources.
    garmin_activity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Duplicate handling (app/services/dedupe.py). Garmin is the main source, so a
    # Strava activity that also exists in Garmin points to the Garmin row here:
    # - duplicate_status "confirmed": same session for sure, never shown nor counted;
    # - duplicate_status "possible": unsure (several candidates), both stay visible.
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("activity.id", ondelete="SET NULL")
    )
    duplicate_status: Mapped[str | None] = mapped_column(String(16))
    # Hidden by hand ("Masquer"): still stored, but not counted anywhere.
    # Like category_override, syncs never touch it.
    hidden: Mapped[bool] = mapped_column(default=False, server_default="0")
    # Where an activity without GPS happened, chosen by hand (None = the default
    # place for its kind, see app/services/places.py). Syncs never touch it.
    place_id: Mapped[int | None] = mapped_column(ForeignKey("place.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    stream: Mapped["ActivityStream | None"] = relationship(
        back_populates="activity", cascade="all, delete-orphan", uselist=False
    )


class ActivityStream(Base):
    """All time series of one activity (GPS, heart rate, altitude, speed, cadence...).

    Stored as one compressed JSON blob instead of one row per second: a 1-hour
    run has ~3,600 points per series, which would mean tens of thousands of
    rows per activity. We always read the series of an activity together, so a
    single compressed blob is much smaller and faster. See
    ``app.services.stream_codec`` for the format.
    """

    __tablename__ = "activity_stream"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activity.id", ondelete="CASCADE"), unique=True
    )
    # Names of the series present, e.g. "time,latlng,heartrate,altitude".
    stream_types: Mapped[str] = mapped_column(String(255))
    point_count: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    activity: Mapped[Activity] = relationship(back_populates="stream")
