"""Evaluation of the AI coaches (phase 5b), run by hand with ``make eval``.

- ``scenarios.py``: "golden" situations on synthetic data, each with what a good
  answer must (and must not) contain;
- ``checks.py``: automatic checks (tools used, numbers, forbidden phrases...);
- ``judge.py``: a model grades each answer on relevance, caution and honesty;
- ``run.py``: runs everything against the real model and writes a report that can
  compare two versions of a prompt.

Tests (tests/test_evals.py) run it with the scripted FakeLLM: CI never pays.
"""
