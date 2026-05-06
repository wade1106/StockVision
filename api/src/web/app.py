import json
import os
import secrets
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.report.prediction_store import build_comparison
from src.notify.webhook import _get_display_name, _load_users, _save_users

app = FastAPI(title="StockVision API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://vision.aurateach.cc"],
    allow_methods=["*"],
    allow_headers=["*"],
)

USERS_FILE = Path("data/users.json")

# 啟動時產生一組 session token，登入後發給前端
_session_token: str | None = None
_bearer = HTTPBearer()


def _valid_token() -> str:
    global _session_token
    if _session_token is None:
        _session_token = secrets.token_hex(32)
    return _session_token


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    if credentials.credentials != _valid_token():
        raise HTTPException(status_code=401, detail="未授權，請重新登入")


class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(body: LoginBody) -> dict:
    expected_user = os.environ.get("ADMIN_USERNAME", "admin")
    expected_pass = os.environ.get("ADMIN_PASSWORD", "")
    if body.username == expected_user and body.password == expected_pass:
        return {"token": _valid_token()}
    raise HTTPException(status_code=401, detail="帳號或密碼錯誤")


@app.post("/api/logout")
def logout(_: None = Depends(require_auth)) -> dict:
    global _session_token
    _session_token = None
    return {"ok": True}


@app.get("/api/users")
def get_users(_: None = Depends(require_auth)) -> dict:
    if not USERS_FILE.exists():
        return {"users": []}
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


@app.post("/api/users/refresh")
def refresh_users(_: None = Depends(require_auth)) -> dict:
    group_id = os.environ.get("LINE_GROUP_ID", "") or None
    data = _load_users()
    updated = 0
    for user in data["users"]:
        is_group_member = user.get("source") in ("group_join", "message", "group_sync")
        name = _get_display_name(
            user["userId"],
            group_id=group_id if is_group_member else None,
        )
        if name != user["userId"] and name != user.get("displayName"):
            user["displayName"] = name
            updated += 1
    _save_users(data)
    return {"updated": updated, "total": len(data["users"])}


@app.get("/api/performance")
def get_performance(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
) -> dict:
    rows = build_comparison(
        date.fromisoformat(start),
        date.fromisoformat(end),
    )
    return {"rows": rows}
