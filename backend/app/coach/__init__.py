"""The AI coaches: one agent engine (engine.py) shared by both coaches.

- ``llm.py`` and ``omniroute.py``: the only places that talk to a model, always
  through OmniRoute (faked in tests);
- ``tools.py``: read-only functions the coach calls to read FRANKS's data;
- ``prompts/``: the versioned system prompts, one file per coach;
- ``costs.py``: token prices and the log of calls (the budget lives in OmniRoute);
- ``history.py``: which messages are sent, and summaries of the older ones;
- ``engine.py``: the loop "model answers -> tools run -> model answers again".
"""
