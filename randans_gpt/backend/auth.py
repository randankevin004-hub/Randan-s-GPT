"""
backend/auth.py
---------------
Supabase email authentication over the plain GoTrue REST API (no extra SDK).

Flows: sign up (+ email confirmation), password sign-in, passwordless 6-digit
code sign-in, password reset by code, profile name update, sign-out.

Security notes
* Only the public *anon* key ever ships with the app (never the service_role key).
* The refresh token is kept in the Windows Credential Manager via `keyring`
  (never in a plain file); the short-lived access token lives only in memory.
* Each account gets its own local database folder (see bridge.py).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

import httpx

from settings.config import app_data_dir, resource_path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
OFFLINE_GRACE_DAYS = 14
SERVICE = "RandansGPT"

FRIENDLY = (
    ("invalid login credentials", "That email or password isn't right."),
    ("email not confirmed", "Please confirm your email first - check your inbox (and spam folder)."),
    ("already registered", "An account with this email already exists. Try signing in instead."),
    ("user already exists", "An account with this email already exists. Try signing in instead."),
    ("token has expired", "That code is wrong or has expired. Request a new one."),
    ("otp_expired", "That code is wrong or has expired. Request a new one."),
    ("invalid refresh token", "Your session expired. Please sign in again."),
    ("rate limit", "Too many attempts. Please wait a minute and try again."),
    ("password should be", None),                      # server text is already clear
    ("same password", "Choose a password you haven't used before."),
    ("signups not allowed", "New sign-ups are currently turned off."),
)


class AuthError(Exception):
    def __init__(self, message: str, code: str = "error") -> None:
        super().__init__(message)
        self.message, self.code = message, code


def load_config() -> dict:
    """Load public app configuration from env, user data or the bundled file."""
    cfg: dict = {}
    for path in (Path(resource_path("supabase.json")), app_data_dir() / "supabase.json"):   # later wins
        try:
            data = json.loads(path.read_text("utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if v not in (None, "")})
        except (OSError, ValueError):
            continue
    cfg["url"] = os.environ.get("SUPABASE_URL") or cfg.get("url", "")
    cfg["anon_key"] = os.environ.get("SUPABASE_ANON_KEY") or cfg.get("anon_key", "")
    req = os.environ.get("RANDANS_REQUIRE_LOGIN")
    cfg["require_login"] = (req.lower() not in ("0", "false", "no")) if req else bool(cfg.get("require_login", True))
    if "YOUR-PROJECT" in cfg["url"] or "YOUR_" in cfg["anon_key"]:          # untouched example file
        cfg["url"] = cfg["anon_key"] = ""
    cfg["url"] = cfg["url"].rstrip("/")
    return cfg


class SessionStore:
    """Keeps the refresh token in the OS credential vault (keyring). Silently does nothing if unavailable."""

    def __init__(self) -> None:
        self._mem: str | None = None

    def load(self) -> dict | None:
        try:
            import keyring
            raw = keyring.get_password(SERVICE, "supabase_session")
        except Exception:  # noqa: BLE001
            raw = self._mem
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    def save(self, blob: dict) -> None:
        raw = json.dumps(blob, separators=(",", ":"))
        try:
            import keyring
            keyring.set_password(SERVICE, "supabase_session", raw)
        except Exception:  # noqa: BLE001
            self._mem = raw
            logging.info("keyring unavailable - session is not persisted")

    def clear(self) -> None:
        self._mem = None
        try:
            import keyring
            keyring.delete_password(SERVICE, "supabase_session")
        except Exception:  # noqa: BLE001
            pass


def _user(raw: dict) -> dict:
    meta = raw.get("user_metadata") or {}
    email = raw.get("email") or ""
    return {"id": raw.get("id"), "email": email,
            "name": meta.get("display_name") or meta.get("full_name") or meta.get("name") or email.split("@")[0],
            "confirmed": bool(raw.get("email_confirmed_at") or raw.get("confirmed_at"))}


class SupabaseAuth:
    def __init__(self, config: dict | None = None, store: SessionStore | None = None) -> None:
        self.config = config or load_config()
        self.store = store or SessionStore()
        self.session: dict | None = None          # {access, refresh, expires_at, user}
        self.offline = False

    # ------------------------------------------------------------ state
    @property
    def configured(self) -> bool:
        return bool(self.config.get("url") and self.config.get("anon_key"))

    @property
    def required(self) -> bool:
        return self.configured and bool(self.config.get("require_login", True))

    @property
    def user(self) -> dict | None:
        return self.session["user"] if self.session else None

    def public_state(self) -> dict:
        return {"configured": self.configured, "required": self.required, "signedIn": self.session is not None,
                "user": self.user, "offline": self.offline}

    # ---------------------------------------------------------- transport
    def _call(self, method: str, path: str, body: dict | None = None, params: dict | None = None,
              token: str | None = None) -> dict:
        headers = {"apikey": self.config["anon_key"], "Content-Type": "application/json",
                   "Authorization": f"Bearer {token or self.config['anon_key']}"}
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.request(method, f"{self.config['url']}/auth/v1{path}", json=body, params=params,
                                      headers=headers)
        except httpx.HTTPError as exc:
            raise AuthError("Can't reach the sign-in service. Check your internet connection.", "network") from exc
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}
        if resp.status_code >= 400:
            raise self._error(resp.status_code, data)
        return data

    @staticmethod
    def _error(status: int, data: dict) -> AuthError:
        raw = " ".join(str(data.get(k, "")) for k in ("error_description", "msg", "message", "error", "error_code")).strip()
        low = raw.lower()
        if status == 429:
            return AuthError(FRIENDLY[6][1], "rate_limit")
        for needle, nice in FRIENDLY:
            if needle in low:
                code = "email_not_confirmed" if "not confirmed" in low else "invalid" if status in (400, 401, 403) else "error"
                return AuthError(nice or (data.get("msg") or data.get("message") or raw), code)
        return AuthError(raw or f"Sign-in service error ({status}).", "error")

    # ----------------------------------------------------------- sessions
    def _apply(self, data: dict) -> dict:
        user = _user(data.get("user") or {})
        self.session = {"access": data["access_token"], "refresh": data["refresh_token"],
                        "expires_at": time.time() + int(data.get("expires_in", 3600)), "user": user}
        self.offline = False
        self.store.save({"rt": data["refresh_token"], "uid": user["id"], "email": user["email"],
                         "name": user["name"], "ts": int(time.time())})
        return user

    def _ok(self, user: dict | None = None, **extra) -> dict:
        return {"ok": True, "user": user or self.user, **extra}

    @staticmethod
    def _fail(exc: AuthError) -> dict:
        return {"ok": False, "error": exc.message, "code": exc.code}

    # ------------------------------------------------------------ actions
    def restore(self) -> dict:
        """On startup: turn the saved refresh token into a live session (tolerates being offline)."""
        blob = self.store.load()
        if not (self.configured and blob and blob.get("rt")):
            return {"ok": False}
        try:
            data = self._call("POST", "/token", {"refresh_token": blob["rt"]}, {"grant_type": "refresh_token"})
            if not data.get("user"):
                data["user"] = self._call("GET", "/user", token=data["access_token"])
            return self._ok(self._apply(data))
        except AuthError as exc:
            if exc.code == "network" and time.time() - blob.get("ts", 0) < OFFLINE_GRACE_DAYS * 86400:
                self.offline = True
                self.session = {"access": "", "refresh": blob["rt"], "expires_at": 0,
                                "user": {"id": blob["uid"], "email": blob["email"], "name": blob["name"], "confirmed": True}}
                return self._ok(offline=True)
            self.store.clear()
            return self._fail(exc)

    def ensure_fresh(self) -> bool:
        """Refresh the access token shortly before it expires. False means the session is gone."""
        s = self.session
        if not s or self.offline and not s["access"]:
            return bool(s)
        if s["expires_at"] - time.time() > 120:
            return True
        try:
            self._apply({**self._call("POST", "/token", {"refresh_token": s["refresh"]}, {"grant_type": "refresh_token"})})
            return True
        except AuthError as exc:
            if exc.code == "network":
                return True
            self.session = None
            self.store.clear()
            return False

    def sign_up(self, email: str, password: str, name: str = "") -> dict:
        try:
            self._validate(email, password)
            data = self._call("POST", "/signup", {"email": email, "password": password,
                                                  "data": {"display_name": name.strip()} if name.strip() else {}})
            if data.get("access_token"):
                return self._ok(self._apply(data))
            return {"ok": True, "needs_confirmation": True, "email": email}
        except AuthError as exc:
            return self._fail(exc)

    def sign_in(self, email: str, password: str) -> dict:
        try:
            self._validate(email, password, signup=False)
            return self._ok(self._apply(self._call("POST", "/token", {"email": email, "password": password},
                                                   {"grant_type": "password"})))
        except AuthError as exc:
            return self._fail(exc)

    def send_code(self, email: str) -> dict:
        try:
            if not EMAIL_RE.match(email.strip()):
                raise AuthError("Enter a valid email address.", "invalid")
            self._call("POST", "/otp", {"email": email.strip(), "create_user": True})
            return {"ok": True, "email": email.strip()}
        except AuthError as exc:
            return self._fail(exc)

    def verify_code(self, email: str, code: str, kind: str = "email") -> dict:
        try:
            code = re.sub(r"\s+", "", code)
            if not re.fullmatch(r"\d{6,8}", code):
                raise AuthError("Enter the 6-digit code from your email.", "invalid")
            data = self._call("POST", "/verify", {"type": kind, "email": email.strip(), "token": code})
            return self._ok(self._apply(data))
        except AuthError as exc:
            return self._fail(exc)

    def resend(self, email: str, kind: str = "signup") -> dict:
        try:
            self._call("POST", "/resend", {"type": kind, "email": email.strip()})
            return {"ok": True}
        except AuthError as exc:
            return self._fail(exc)

    def reset_password(self, email: str) -> dict:
        try:
            if not EMAIL_RE.match(email.strip()):
                raise AuthError("Enter a valid email address.", "invalid")
            self._call("POST", "/recover", {"email": email.strip()})
            return {"ok": True, "email": email.strip()}
        except AuthError as exc:
            return self._fail(exc)

    def set_password(self, password: str) -> dict:
        try:
            if len(password) < 8:
                raise AuthError("Use at least 8 characters.", "invalid")
            self._call("PUT", "/user", {"password": password}, token=self._token())
            return {"ok": True}
        except AuthError as exc:
            return self._fail(exc)

    def update_name(self, name: str) -> dict:
        try:
            raw = self._call("PUT", "/user", {"data": {"display_name": name}}, token=self._token())
            if self.session:
                self.session["user"] = _user(raw)
                self.store.save({"rt": self.session["refresh"], "uid": self.user["id"], "email": self.user["email"],
                                 "name": self.user["name"], "ts": int(time.time())})
            return self._ok()
        except AuthError as exc:
            return self._fail(exc)

    def sign_out(self) -> dict:
        token = self.session["access"] if self.session else None
        self.session, self.offline = None, False
        self.store.clear()
        if token:
            try:
                self._call("POST", "/logout", token=token)
            except AuthError:
                pass                                    # local sign-out already happened
        return {"ok": True}

    # ------------------------------------------------------------ helpers
    def _token(self) -> str:
        if not self.session or not self.session["access"]:
            raise AuthError("You're offline or signed out. Sign in again.", "invalid")
        self.ensure_fresh()
        return self.session["access"] if self.session else ""

    @staticmethod
    def _validate(email: str, password: str, signup: bool = True) -> None:
        if not EMAIL_RE.match(email.strip()):
            raise AuthError("Enter a valid email address.", "invalid")
        if not password or (signup and len(password) < 8):
            raise AuthError("Use a password with at least 8 characters.", "invalid")
