"""Health data sources (sleep, resting heart rate, HRV...) behind one interface.

The rest of the app only knows :class:`~app.integrations.health.provider.HealthDataProvider`.
Garmin through the unofficial library, or plain file import, can be swapped
without touching anything else.
"""
