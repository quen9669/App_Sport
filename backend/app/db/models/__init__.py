"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.db.models.activity import Activity, ActivityStream
from app.db.models.credential import SourceCredential
from app.db.models.health import DailyHealth, SleepNight
from app.db.models.profile import UserProfile
from app.db.models.raw import RawPayload
from app.db.models.sync import SyncCursor, SyncLog

__all__ = [
    "Activity",
    "ActivityStream",
    "DailyHealth",
    "RawPayload",
    "SleepNight",
    "SourceCredential",
    "SyncCursor",
    "SyncLog",
    "UserProfile",
]
