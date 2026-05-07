import os
import json
import secrets
import datetime as dt
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List
import mimetypes

import requests
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production-!@#$%")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "512")) * 1024 * 1024

# Cookie/session hardening (works fine on Vercel too)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
if os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}:
    app.config["SESSION_COOKIE_SECURE"] = True

# Database: use DATABASE_URL (Postgres) if provided, else local sqlite
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL:
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    # Vercel serverless: use /tmp (writable) instead of project dir
    if os.environ.get("VERCEL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/app.db"
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
DB_READY = False


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: dt.datetime.utcnow(), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: dt.datetime.utcnow(), onupdate=lambda: dt.datetime.utcnow(), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@local.dev").strip().lower()
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin@123456")


class SocialAccount(db.Model):
    __tablename__ = "social_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    # provider: google, youtube, facebook_page, tiktok
    provider = db.Column(db.String(50), nullable=False, index=True)
    external_id = db.Column(db.String(255), nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=True)

    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    token_type = db.Column(db.String(50), nullable=True)
    scopes = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)

    status = db.Column(db.String(20), nullable=False, default="connected", index=True)  # connected | expired | error | disconnected
    last_error = db.Column(db.Text, nullable=True)
    meta_json = db.Column(db.Text, nullable=True)  # JSON string (pages/channel info, etc.)

    created_at = db.Column(db.DateTime, default=lambda: dt.datetime.utcnow(), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: dt.datetime.utcnow(), onupdate=lambda: dt.datetime.utcnow(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "provider", "external_id", name="uq_social_account"),
    )

    def as_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "external_id": self.external_id,
            "display_name": self.display_name,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_error": self.last_error,
            "meta": json.loads(self.meta_json) if self.meta_json else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def _initialize_database() -> None:
    db.create_all()

    # Bootstrap a default account for first login.
    # This only creates the user if it does not exist yet.
    if DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD:
        existing_admin = User.query.filter_by(email=DEFAULT_ADMIN_EMAIL).first()
        if not existing_admin:
            seeded = User(email=DEFAULT_ADMIN_EMAIL)
            seeded.set_password(DEFAULT_ADMIN_PASSWORD)
            db.session.add(seeded)
            db.session.commit()


with app.app_context():
    try:
        _initialize_database()
        DB_READY = True
    except Exception as e:
        # Avoid hard-crash at import time in serverless runtime.
        print(f"[DB INIT ERROR] {e}")


@app.before_request
def _ensure_db_ready():
    global DB_READY
    if DB_READY:
        return
    try:
        _initialize_database()
        DB_READY = True
    except Exception as e:
        print(f"[DB RETRY ERROR] {e}")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


oauth = OAuth(app)

# -----------------------
# OAuth registrations
# -----------------------
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/youtube.readonly",
        "prompt": "consent",
        "access_type": "offline",
    },
)

oauth.register(
    name="facebook",
    client_id=os.environ.get("FACEBOOK_CLIENT_ID"),
    client_secret=os.environ.get("FACEBOOK_CLIENT_SECRET"),
    access_token_url="https://graph.facebook.com/v19.0/oauth/access_token",
    authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
    api_base_url="https://graph.facebook.com/v19.0/",
    client_kwargs={"scope": "pages_show_list,pages_read_engagement,pages_manage_posts"},
)

oauth.register(
    name="tiktok",
    client_id=os.environ.get("TIKTOK_CLIENT_KEY"),
    client_secret=os.environ.get("TIKTOK_CLIENT_SECRET"),
    authorize_url="https://www.tiktok.com/v2/auth/authorize/",
    access_token_url="https://open.tiktokapis.com/v2/oauth/token/",
    api_base_url="https://open.tiktokapis.com/",
    client_kwargs={"scope": "user.info.basic"},
)


def _now_utc() -> dt.datetime:
    return dt.datetime.utcnow()

FB_ACTIVE_SESSION_KEY = "active_facebook_page_id"


def _set_status_from_expiry(acc: SocialAccount) -> None:
    if acc.status == "disconnected":
        return
    if acc.expires_at and acc.expires_at <= _now_utc():
        acc.status = "expired"
    elif acc.status in {"expired", "error"}:
        # if we have a fresh token again, caller can set connected explicitly
        pass


def _require_env(keys: List[str]) -> None:
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        abort(500, description=f"Thiếu cấu hình ENV: {', '.join(missing)}")

def _has_env(*keys: str) -> bool:
    return all(bool(os.environ.get(k)) for k in keys)

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def _allowed_emails() -> set[str]:
    values: set[str] = set()
    for key in ("AUTH_ALLOWED_EMAILS", "ADMIN_EMAIL"):
        raw = os.environ.get(key, "")
        if not raw:
            continue
        for part in raw.replace(";", ",").split(","):
            email = part.strip().lower()
            if email:
                values.add(email)
    if DEFAULT_ADMIN_EMAIL:
        values.add(DEFAULT_ADMIN_EMAIL)
    return values

def _is_email_allowed(email: str) -> bool:
    allowed = _allowed_emails()
    if not allowed:
        # If no whitelist configured, do not block existing users by config absence.
        return True
    return email.strip().lower() in allowed

def _registration_enabled() -> bool:
    # Default OFF for private/internal app. Turn on with REGISTRATION_ENABLED=true.
    return _env_flag("REGISTRATION_ENABLED", default=False)

def _registration_allowed_for_email(email: str) -> bool:
    if not _registration_enabled():
        return False
    return _is_email_allowed(email)


def _save_or_update_account(
    *,
    provider: str,
    external_id: str,
    display_name: Optional[str],
    access_token: Optional[str],
    refresh_token: Optional[str],
    token_type: Optional[str],
    scopes: Optional[str],
    expires_in: Optional[int],
    meta: Optional[Dict[str, Any]] = None,
) -> SocialAccount:
    expires_at = None
    if expires_in:
        expires_at = _now_utc() + dt.timedelta(seconds=int(expires_in))
    acc = SocialAccount.query.filter_by(user_id=current_user.id, provider=provider, external_id=external_id).first()
    if not acc:
        acc = SocialAccount(user_id=current_user.id, provider=provider, external_id=external_id)
        db.session.add(acc)
    acc.display_name = display_name
    if access_token:
        acc.access_token = access_token
    if refresh_token:
        acc.refresh_token = refresh_token
    acc.token_type = token_type
    acc.scopes = scopes
    acc.expires_at = expires_at
    acc.status = "connected"
    acc.last_error = None
    acc.meta_json = json.dumps(meta) if meta else None
    _set_status_from_expiry(acc)
    db.session.commit()
    return acc


# ============================================================
# Auth
# ============================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = request.args.get("error") or None
    if request.method == "GET" and not _registration_enabled():
        return redirect(url_for("login", error="Đăng ký đang bị khóa. Liên hệ quản trị viên để cấp quyền tài khoản."))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not _registration_enabled():
            error = "Đăng ký đang bị khóa. Liên hệ quản trị viên để được tạo tài khoản."
        elif not email or not password:
            error = "Vui lòng nhập email và mật khẩu."
        elif len(password) < 8:
            error = "Mật khẩu tối thiểu 8 ký tự."
        elif not _registration_allowed_for_email(email):
            error = "Email này chưa được cấp quyền đăng ký."
        elif User.query.filter_by(email=email).first():
            error = "Email đã tồn tại."
        else:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for("index"))
    return render_template(
        "register.html",
        error=error,
        google_enabled=_has_env("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        registration_enabled=_registration_enabled(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = request.args.get("error") or None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not _is_email_allowed(email):
            error = "Tài khoản chưa được cấp quyền truy cập hệ thống."
        elif not user or not user.check_password(password):
            error = "Email hoặc mật khẩu không đúng!"
        else:
            login_user(user, remember=True)
            return redirect(url_for("index"))
    return render_template(
        "login.html",
        error=error,
        google_enabled=_has_env("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        registration_enabled=_registration_enabled(),
    )


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/auth/google/login")
def google_login():
    if not _has_env("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        # Avoid 500: let user continue with email/password
        return redirect(url_for("login", error="Chưa cấu hình Google OAuth (thiếu GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)."))
    nonce = secrets.token_urlsafe(16)
    return oauth.google.authorize_redirect(url_for("google_callback", _external=True), nonce=nonce)


@app.route("/auth/google/callback")
def google_callback():
    if not _has_env("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        return redirect(url_for("login", error="Chưa cấu hình Google OAuth (thiếu GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)."))
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = oauth.google.parse_id_token(token)

    email = (userinfo.get("email") or "").lower()
    if not email:
        abort(400, description="Không lấy được email từ Google.")
    if not _is_email_allowed(email):
        return redirect(url_for("login", error="Email Google này chưa được cấp quyền truy cập hệ thống."))

    user = User.query.filter_by(email=email).first()
    if not user:
        if not _registration_allowed_for_email(email):
            return redirect(url_for("login", error="Đăng ký tự động bằng Google đang bị khóa cho email này."))
        user = User(email=email)
        db.session.add(user)
        db.session.commit()
    login_user(user, remember=True)

    # Save Google identity (for login trace) and YouTube channels (as separate accounts)
    _save_or_update_account(
        provider="google",
        external_id=userinfo.get("sub") or email,
        display_name=userinfo.get("name") or email,
        access_token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_type=token.get("token_type"),
        scopes=token.get("scope"),
        expires_in=token.get("expires_in"),
        meta={"email": email},
    )

    # Fetch YouTube channels (if scope granted)
    try:
        yt = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {token.get('access_token')}"},
            timeout=20,
        )
        yt_data = yt.json()
        if yt.status_code == 200 and yt_data.get("items"):
            for item in yt_data["items"]:
                ch_id = item.get("id")
                title = (item.get("snippet") or {}).get("title")
                if ch_id:
                    _save_or_update_account(
                        provider="youtube",
                        external_id=ch_id,
                        display_name=title or ch_id,
                        access_token=token.get("access_token"),
                        refresh_token=token.get("refresh_token"),
                        token_type=token.get("token_type"),
                        scopes=token.get("scope"),
                        expires_in=token.get("expires_in"),
                        meta={"raw": item},
                    )
    except Exception:
        # Don't block login if YouTube API fails
        pass

    return redirect(url_for("index"))


# ============================================================
# Connections (OAuth)
# ============================================================
@app.route("/connect/facebook")
@login_required
def connect_facebook():
    _require_env(["FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"])
    return oauth.facebook.authorize_redirect(url_for("facebook_callback", _external=True))


@app.route("/connect/facebook/callback")
@login_required
def facebook_callback():
    _require_env(["FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"])
    token = oauth.facebook.authorize_access_token()
    access_token = token.get("access_token")
    if not access_token:
        abort(400, description="Không lấy được access_token Facebook.")

    # Get pages the user can access
    pages = requests.get(
        "https://graph.facebook.com/v19.0/me/accounts",
        params={"fields": "id,name,access_token", "access_token": access_token},
        timeout=20,
    )
    pages_data = pages.json()
    if pages.status_code != 200:
        abort(400, description=f"Facebook lỗi: {pages_data}")

    for p in pages_data.get("data", []):
        page_id = p.get("id")
        page_name = p.get("name")
        page_token = p.get("access_token")
        if not page_id or not page_token:
            continue
        # Facebook page tokens often are long-lived; no refresh_token. We'll mark expires_at null.
        _save_or_update_account(
            provider="facebook_page",
            external_id=page_id,
            display_name=page_name or page_id,
            access_token=page_token,
            refresh_token=None,
            token_type="bearer",
            scopes=None,
            expires_in=None,
            meta={"page": p},
        )

    return redirect(url_for("index"))


@app.route("/connect/tiktok")
@login_required
def connect_tiktok():
    _require_env(["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"])
    redirect_uri = url_for("tiktok_callback", _external=True)
    state = secrets.token_urlsafe(16)
    # TikTok expects client_key param name; Authlib uses client_id internally, so craft URL explicitly.
    params = {
        "client_key": os.environ.get("TIKTOK_CLIENT_KEY"),
        "scope": "user.info.basic",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return redirect(f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}")


@app.route("/connect/tiktok/callback")
@login_required
def tiktok_callback():
    _require_env(["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"])
    code = request.args.get("code")
    if not code:
        abort(400, description="Thiếu code từ TikTok.")
    redirect_uri = url_for("tiktok_callback", _external=True)

    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ.get("TIKTOK_CLIENT_KEY"),
            "client_secret": os.environ.get("TIKTOK_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=20,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        abort(400, description=f"TikTok lỗi token: {data}")

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in")

    # Fetch basic user info to get open_id / display name
    info = requests.get(
        "https://open.tiktokapis.com/v2/user/info/",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"fields": "open_id,union_id,display_name,avatar_url"},
        timeout=20,
    )
    info_data = info.json()
    user_data = (info_data.get("data") or {}).get("user") or {}
    open_id = user_data.get("open_id") or data.get("open_id") or user_data.get("union_id")
    display_name = user_data.get("display_name") or open_id
    if not open_id:
        open_id = f"tiktok:{current_user.id}"

    _save_or_update_account(
        provider="tiktok",
        external_id=open_id,
        display_name=display_name,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=data.get("token_type"),
        scopes=data.get("scope"),
        expires_in=expires_in,
        meta={"user": user_data, "raw_token": {k: data.get(k) for k in ["expires_in", "scope"]}},
    )

    return redirect(url_for("index"))


@app.route("/connect/youtube")
@login_required
def connect_youtube():
    # YouTube connection is the same as Google OAuth scopes we registered
    return redirect(url_for("google_login"))

@app.route("/api/connect/facebook/manual", methods=["POST"])
@login_required
def api_connect_facebook_manual():
    data = request.json or {}
    fanpage_id = (data.get("fanpageID") or "").strip()
    token = (data.get("token") or "").strip()
    if not fanpage_id or not token:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ Fanpage ID và Token."}), 400

    try:
        validation_url = f"https://graph.facebook.com/v19.0/{fanpage_id}"
        resp = requests.get(
            validation_url,
            params={"fields": "id,name", "access_token": token},
            timeout=20,
        )
        val_data = resp.json()
        if resp.status_code != 200:
            error_msg = (val_data.get("error") or {}).get("message") or str(val_data)
            return jsonify({"status": "error", "message": f"Facebook báo lỗi: {error_msg}"}), 400

        page_name = val_data.get("name") or fanpage_id
        _save_or_update_account(
            provider="facebook_page",
            external_id=fanpage_id,
            display_name=page_name,
            access_token=token,
            refresh_token=None,
            token_type="bearer",
            scopes=None,
            expires_in=None,
            meta={"page": val_data, "manual": True},
        )
        return jsonify({"status": "success", "message": f"Đã kết nối Fanpage: {page_name} ({fanpage_id})"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route("/api/connect/tiktok/manual", methods=["POST"])
@login_required
def api_connect_tiktok_manual():
    data = request.json or {}
    open_id = (data.get("open_id") or "").strip()
    token = (data.get("token") or "").strip()
    if not open_id or not token:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ Open ID và Access Token."}), 400

    try:
        info = requests.get(
            "https://open.tiktokapis.com/v2/user/info/",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "open_id,union_id,display_name,avatar_url"},
            timeout=20,
        )
        info_data = info.json()
        if info.status_code != 200:
            return jsonify({"status": "error", "message": f"TikTok báo lỗi: {info_data}"}), 400

        user_data = (info_data.get("data") or {}).get("user") or {}
        if user_data.get("open_id") and user_data.get("open_id") != open_id:
            open_id = user_data.get("open_id")

        display_name = user_data.get("display_name") or open_id
        _save_or_update_account(
            provider="tiktok",
            external_id=open_id,
            display_name=display_name,
            access_token=token,
            refresh_token=None,
            token_type="bearer",
            scopes=None,
            expires_in=None,
            meta={"user": user_data, "manual": True},
        )
        return jsonify({"status": "success", "message": f"Đã kết nối TikTok: {display_name} ({open_id})"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route("/api/connect/youtube/manual", methods=["POST"])
@login_required
def api_connect_youtube_manual():
    data = request.json or {}
    channel_id = (data.get("channel_id") or "").strip()
    token = (data.get("token") or "").strip()
    if not channel_id or not token:
        return jsonify({"status": "error", "message": "Vui lòng nhập đầy đủ Channel ID và Access Token."}), 400

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "id": channel_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        yt_data = resp.json()
        if resp.status_code != 200:
            return jsonify({"status": "error", "message": f"YouTube báo lỗi: {yt_data}"}), 400
        items = yt_data.get("items") or []
        if not items:
            return jsonify({"status": "error", "message": "Không tìm thấy channel. Kiểm tra lại Channel ID/token."}), 400
        item = items[0]
        title = ((item.get("snippet") or {}).get("title")) or channel_id

        _save_or_update_account(
            provider="youtube",
            external_id=channel_id,
            display_name=title,
            access_token=token,
            refresh_token=None,
            token_type="bearer",
            scopes=None,
            expires_in=None,
            meta={"raw": item, "manual": True},
        )
        return jsonify({"status": "success", "message": f"Đã kết nối YouTube: {title} ({channel_id})"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


# ============================================================
# App pages / APIs
# ============================================================
@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        user=current_user,
        google_enabled=_has_env("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
        facebook_enabled=_has_env("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_SECRET"),
        tiktok_enabled=_has_env("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"),
    )


@app.route("/api/me")
@login_required
def api_me():
    return jsonify({"id": current_user.id, "email": current_user.email})


@app.route("/api/connections", methods=["GET"])
@login_required
def api_connections():
    accounts = SocialAccount.query.filter_by(user_id=current_user.id).order_by(SocialAccount.updated_at.desc()).all()
    for a in accounts:
        _set_status_from_expiry(a)
    db.session.commit()
    return jsonify({"status": "success", "accounts": [a.as_dict() for a in accounts]})


@app.route("/api/connections/<int:account_id>/disconnect", methods=["POST"])
@login_required
def api_disconnect(account_id: int):
    acc = SocialAccount.query.filter_by(id=account_id, user_id=current_user.id).first()
    if not acc:
        return jsonify({"status": "error", "message": "Không tìm thấy kết nối."}), 404
    acc.status = "disconnected"
    acc.access_token = None
    acc.refresh_token = None
    acc.expires_at = None
    db.session.commit()
    return jsonify({"status": "success"})


def _refresh_google_or_youtube(acc: SocialAccount) -> bool:
    if not acc.refresh_token:
        return False
    _require_env(["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"])
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "grant_type": "refresh_token",
            "refresh_token": acc.refresh_token,
        },
        timeout=20,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        acc.status = "error"
        acc.last_error = f"Google refresh error: {data}"
        db.session.commit()
        return False

    acc.access_token = data.get("access_token")
    acc.token_type = data.get("token_type") or acc.token_type
    if data.get("expires_in"):
        acc.expires_at = _now_utc() + dt.timedelta(seconds=int(data["expires_in"]))
    acc.status = "connected"
    acc.last_error = None
    db.session.commit()
    return True


def _refresh_tiktok(acc: SocialAccount) -> bool:
    if not acc.refresh_token:
        return False
    _require_env(["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"])
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ.get("TIKTOK_CLIENT_KEY"),
            "client_secret": os.environ.get("TIKTOK_CLIENT_SECRET"),
            "grant_type": "refresh_token",
            "refresh_token": acc.refresh_token,
        },
        timeout=20,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        acc.status = "error"
        acc.last_error = f"TikTok refresh error: {data}"
        db.session.commit()
        return False

    acc.access_token = data.get("access_token")
    if data.get("refresh_token"):
        acc.refresh_token = data.get("refresh_token")
    if data.get("expires_in"):
        acc.expires_at = _now_utc() + dt.timedelta(seconds=int(data["expires_in"]))
    acc.status = "connected"
    acc.last_error = None
    db.session.commit()
    return True


@app.route("/api/connections/refresh", methods=["POST"])
@login_required
def api_refresh_connections():
    accounts = SocialAccount.query.filter_by(user_id=current_user.id).all()
    refreshed = 0
    for acc in accounts:
        _set_status_from_expiry(acc)
        if acc.status != "expired":
            continue
        if acc.provider in {"google", "youtube"}:
            if _refresh_google_or_youtube(acc):
                refreshed += 1
        elif acc.provider == "tiktok":
            if _refresh_tiktok(acc):
                refreshed += 1
    return jsonify({"status": "success", "refreshed": refreshed})


# ============================================================
# Auto-post endpoints (Facebook scheduled posts)
# ============================================================
import poster


def _get_active_facebook_page():
    active_id = session.get(FB_ACTIVE_SESSION_KEY)
    if active_id:
        acc = (
            SocialAccount.query.filter_by(user_id=current_user.id, provider="facebook_page", external_id=str(active_id))
            .filter(SocialAccount.status.in_(["connected", "expired", "error"]))
            .first()
        )
        if acc and acc.access_token:
            _set_status_from_expiry(acc)
            if acc.status == "expired":
                db.session.commit()
                return None
            db.session.commit()
            return acc
        # selection no longer valid
        session.pop(FB_ACTIVE_SESSION_KEY, None)

    acc = (
        SocialAccount.query.filter_by(user_id=current_user.id, provider="facebook_page")
        .filter(SocialAccount.status.in_(["connected", "expired", "error"]))
        .order_by(SocialAccount.updated_at.desc())
        .first()
    )
    if not acc or not acc.access_token:
        return None
    _set_status_from_expiry(acc)
    if acc.status == "expired":
        # Facebook page tokens usually don't have refresh_token; mark expired and let user reconnect.
        db.session.commit()
        return None
    db.session.commit()
    return acc


@app.route("/api/facebook/pages", methods=["GET"])
@login_required
def api_facebook_pages():
    pages = (
        SocialAccount.query.filter_by(user_id=current_user.id, provider="facebook_page")
        .filter(SocialAccount.status.in_(["connected", "expired", "error"]))
        .order_by(SocialAccount.display_name.asc())
        .all()
    )
    active_id = session.get(FB_ACTIVE_SESSION_KEY)
    return jsonify(
        {
            "status": "success",
            "active_page_id": active_id,
            "pages": [
                {
                    "external_id": p.external_id,
                    "display_name": p.display_name or p.external_id,
                    "status": p.status,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in pages
            ],
        }
    )


@app.route("/api/facebook/active", methods=["GET", "POST"])
@login_required
def api_facebook_active():
    if request.method == "GET":
        active_id = session.get(FB_ACTIVE_SESSION_KEY)
        return jsonify({"status": "success", "active_page_id": active_id})

    data = request.json or {}
    page_id = (data.get("page_id") or "").strip()
    if not page_id:
        return jsonify({"status": "error", "message": "Thiếu page_id"}), 400
    acc = SocialAccount.query.filter_by(user_id=current_user.id, provider="facebook_page", external_id=page_id).first()
    if not acc:
        return jsonify({"status": "error", "message": "Page không tồn tại trong danh sách kết nối."}), 404
    session[FB_ACTIVE_SESSION_KEY] = page_id
    return jsonify({"status": "success"})


@app.route("/api/post/tiktok", methods=["POST"])
@login_required
def api_post_tiktok():
    # Minimal implementation: requires video URL in request
    data = request.json or {}
    account_id = (data.get("account_id") or "").strip()
    video_url = (data.get("video_url") or "").strip()
    caption = (data.get("caption") or "").strip()
    if not account_id or not video_url:
        return jsonify(
            {
                "status": "error",
                "message": "TikTok API cần video_url. Vui lòng truyền account_id + video_url (link video public) để đăng.",
            }
        ), 400

    acc = SocialAccount.query.filter_by(user_id=current_user.id, provider="tiktok", external_id=account_id).first()
    if not acc or not acc.access_token:
        return jsonify({"status": "error", "message": "Chưa kết nối TikTok account này."}), 400

    # TikTok Content Posting API varies by app permissions; we keep a safe message if not available.
    try:
        resp = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/",
            headers={"Authorization": f"Bearer {acc.access_token}", "Content-Type": "application/json"},
            json={
                "post_info": {"title": caption[:150] if caption else ""},
                "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
            },
            timeout=30,
        )
        out = resp.json()
        if resp.status_code != 200:
            return jsonify({"status": "error", "message": f"TikTok báo lỗi: {out}"}), 400
        return jsonify({"status": "success", "result": out})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route("/api/post/youtube", methods=["POST"])
@login_required
def api_post_youtube():
    # Safest & most convenient: user uploads a file, we do resumable upload to YouTube.
    channel_id = (request.form.get("channel_id") or "").strip()
    title = (request.form.get("title") or "").strip() or "Auto Upload"
    description = (request.form.get("description") or "").strip()
    privacy = (request.form.get("privacy_status") or "private").strip()
    f = request.files.get("video")

    if not channel_id:
        return jsonify({"status": "error", "message": "Thiếu channel_id"}), 400
    if not f:
        return jsonify({"status": "error", "message": "Thiếu file video (field name: video)"}), 400

    acc = SocialAccount.query.filter_by(user_id=current_user.id, provider="youtube", external_id=channel_id).first()
    if not acc or not acc.access_token:
        return jsonify({"status": "error", "message": "Chưa kết nối YouTube channel này."}), 400

    _set_status_from_expiry(acc)
    if acc.status == "expired":
        # Try refresh if possible (OAuth connections will have refresh_token)
        if not _refresh_google_or_youtube(acc):
            return jsonify({"status": "error", "message": "Token YouTube đã hết hạn và không refresh được. Hãy connect lại bằng Google OAuth."}), 400

    try:
        # Save to temp file
        tmp_dir = os.path.join(os.getcwd(), "tmp_uploads")
        os.makedirs(tmp_dir, exist_ok=True)
        filename = secrets.token_hex(8) + "_" + (f.filename or "video")
        tmp_path = os.path.join(tmp_dir, filename)
        f.save(tmp_path)

        size = os.path.getsize(tmp_path)
        mime = mimetypes.guess_type(tmp_path)[0] or "video/mp4"

        init_resp = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {acc.access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime,
                "X-Upload-Content-Length": str(size),
            },
            json={
                "snippet": {"title": title[:100], "description": description[:5000]},
                "status": {"privacyStatus": privacy},
            },
            timeout=30,
        )
        if init_resp.status_code not in (200, 201):
            return jsonify({"status": "error", "message": f"YouTube init lỗi: {init_resp.text}"}), 400

        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            return jsonify({"status": "error", "message": "YouTube không trả Location upload URL."}), 400

        with open(tmp_path, "rb") as fp:
            put_resp = requests.put(
                upload_url,
                headers={"Content-Type": mime, "Content-Length": str(size)},
                data=fp,
                timeout=1200,
            )

        try:
            out = put_resp.json()
        except Exception:
            out = {"raw": put_resp.text}

        if put_resp.status_code not in (200, 201):
            return jsonify({"status": "error", "message": f"YouTube upload lỗi: {out}"}), 400

        return jsonify({"status": "success", "result": out})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}), 500


@app.route("/api/run_script", methods=["POST"])
@login_required
def run_script():
    fb = _get_active_facebook_page()
    if not fb:
        return jsonify({"status": "error", "message": "Chưa kết nối Facebook Page (hoặc token hết hạn)."}), 400
    try:
        output = poster.run_auto_post(fanpage_id=fb.external_id, access_token=fb.access_token)
        return jsonify(
            {
                "status": "success" if "Thành công" in output else "error",
                "output": output,
                "error": "" if "Thành công" in output else output,
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/scheduled_posts", methods=["GET"])
@login_required
def get_scheduled_posts():
    fb = _get_active_facebook_page()
    if not fb:
        return jsonify({"status": "error", "message": "Chưa kết nối Facebook Page (hoặc token hết hạn)."}), 400

    url = f"https://graph.facebook.com/v19.0/{fb.external_id}/scheduled_posts"
    try:
        response = requests.get(
            url,
            params={"fields": "id,message,created_time,scheduled_publish_time,attachments", "access_token": fb.access_token},
            timeout=20,
        )
        data = response.json()
        if "data" in data:
            return jsonify({"status": "success", "posts": data["data"]})
        return jsonify({"status": "error", "message": str(data)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/scheduled_posts/<post_id>", methods=["DELETE"])
@login_required
def delete_post(post_id):
    fb = _get_active_facebook_page()
    if not fb:
        return jsonify({"status": "error", "message": "Chưa kết nối Facebook Page (hoặc token hết hạn)."}), 400

    url = f"https://graph.facebook.com/{post_id}"
    try:
        response = requests.delete(url, params={"access_token": fb.access_token}, timeout=20)
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Đã xoá bài viết thành công"})
        return jsonify({"status": "error", "message": response.text}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
