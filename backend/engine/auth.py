"""Accounts: scrypt password hashes and a signed, expiring session cookie (standard library only)."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from pathlib import Path

COOKIE = "kinara_session"
MAX_AGE = 14 * 24 * 3600
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,120}\.[^@\s]{2,}$")


def enabled():
    return os.environ.get("KINARA_AUTH", "on").lower() not in ("off", "0", "false")


def _secret():
    s = os.environ.get("KINARA_SECRET")
    if s:
        return s.encode()
    f = Path("data") / "secret.key"
    f.parent.mkdir(exist_ok=True)
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip().encode()


def hash_password(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(pw, stored):
    try:
        _, s, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(s), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:
        return False


def _sig(payload):
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(uid, now=None):
    exp = int((time.time() if now is None else now) + MAX_AGE)
    p = f"{uid}.{exp}"
    return p + "." + _sig(p)


def read_token(token, now=None):
    try:
        uid, exp, sig = token.split(".")
        if not hmac.compare_digest(sig, _sig(f"{uid}.{exp}")) or int(exp) < (time.time() if now is None else now):
            return None
        return int(uid)
    except Exception:
        return None


def clean_email(e):
    e = (e or "").strip().lower()
    return e if EMAIL.match(e) else None


def password_ok(pw):
    return isinstance(pw, str) and 8 <= len(pw) <= 128
