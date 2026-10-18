"""Backend of the personal sport app.

The code is organised in layers so that each file has one job:
- ``app.api``: HTTP routes (what URL does what), kept thin;
- ``app.services`` (coming in phase 1): business logic;
- ``app.repositories`` (coming in phase 1): database access.
"""
