"""The AI coaches: one agent engine (engine.py) shared by both coaches.

- ``llm.py`` and ``gemini.py``: the only places that talk to a model API, Claude
  or Gemini (faked in tests);
- ``tools.py``: read-only functions the coach calls to read FRANKS's data;
- ``prompts/``: the versioned system prompts, one file per coach;
- ``costs.py``: token prices, the log of calls and the monthly budget;
- ``history.py``: which messages are sent, and summaries of the older ones;
- ``engine.py``: the loop "model answers -> tools run -> model answers again".
"""
