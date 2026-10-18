"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.db.models.activity import Activity, ActivityStream
from app.db.models.credential import SourceCredential
from app.db.models.goal import Goal
from app.db.models.health import DailyHealth, SleepNight
from app.db.models.profile import BodyMetric, UserProfile
from app.db.models.raw import RawPayload
from app.db.models.strength import StrengthSession, StrengthSet
from app.db.models.sync import SyncCursor, SyncLog

__all__ = [
    "Activity",
    "ActivityStream",
    "BodyMetric",
    "DailyHealth",
    "Goal",
    "RawPayload",
    "SleepNight",
    "SourceCredential",
    "StrengthSession",
    "StrengthSet",
    "SyncCursor",
    "SyncLog",
    "UserProfile",
]
