"""Race predictor (phase 4): pure calculations, no database, no web.

- ``daniels``: VDOT from a race time, race times and training paces from a VDOT.
- ``riegel``: the simple distance/time scaling formula.
- ``plan``: pace plan with kilometre splits, and how realistic a target time is.
- ``efforts``: which runs say something about the current form, and the estimate.

The AI coach (phase 5) reads these results; it never computes them itself.
"""
