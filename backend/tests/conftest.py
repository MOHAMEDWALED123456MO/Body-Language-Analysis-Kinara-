"""Existing tests run with accounts off and a throwaway database. test_accounts.py switches accounts on itself."""
import os
import tempfile

os.environ.setdefault("KINARA_AUTH", "off")
os.environ["KINARA_DB"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(prefix="kinara_test_"), "t.db")
os.environ.setdefault("KINARA_SECRET", "test-secret")
