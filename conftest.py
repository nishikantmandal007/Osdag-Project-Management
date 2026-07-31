"""Present so pytest puts the repo root on sys.path.

Without a package install, ``pytest tests/`` (the console script) inserts only
``tests/`` onto ``sys.path`` and ``import pm`` fails — whereas ``python -m pytest``
happens to add the current directory and masks the problem. A root-level
conftest makes pytest add this directory regardless of how it is invoked, so CI
(`pytest -q tests/`) and local (`python -m pytest`) agree. There is no packaging
to `pip install -e`, and this is smaller than adding one for tests alone.
"""
