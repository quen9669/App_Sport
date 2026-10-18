"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.db.models.activity import Activity, ActivityStream
from app.db.models.coach import CoachCall, CoachConversation, CoachMemory, CoachMessage
from app.db.models.credential import SourceCredential
from app.db.models.goal import Goal
from app.db.models.health import DailyHealth, SleepNight
from app.db.models.place import Place
from app.db.models.profile import BodyMetric, UserProfile
from app.db.models.race import RaceTarget
from app.db.models.raw import RawPayload
from app.db.models.smoking import SmokingDay
from app.db.models.strength import StrengthSession, StrengthSet
from app.db.models.sync import SyncCursor, SyncLog

__all__ = [
    "Activity",
    "ActivityStream",
    "BodyMetric",
    "CoachCall",
    "CoachConversation",
    "CoachMemory",
    "CoachMessage",
    "DailyHealth",
    "Goal",
    "Place",
    "RaceTarget",
    "RawPayload",
    "SleepNight",
    "SmokingDay",
    "SourceCredential",
    "StrengthSession",
    "StrengthSet",
    "SyncCursor",
    "SyncLog",
    "UserProfile",
]
