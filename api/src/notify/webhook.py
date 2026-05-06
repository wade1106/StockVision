import hashlib
import hmac
import json
import logging
import os
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import FastAPI, Header, HTTPException, Request

logger = logging.getLogger(__name__)

app = FastAPI(title="StockVision LINE Webhook")

USERS_FILE = Path("data/users.json")
LINE_PROFILE_URL = "https://api.line.me/v2/bot/profile/{user_id}"
LINE_GROUP_MEMBER_URL = "https://api.line.me/v2/bot/group/{group_id}/member/{user_id}"


def _load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {"users": []}


def _save_users(data: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# 已知成員快取，避免每次收訊息都讀檔
_known_user_ids: set[str] | None = None


def _get_known_ids() -> set[str]:
    global _known_user_ids
    if _known_user_ids is None:
        _known_user_ids = {u["userId"] for u in _load_users()["users"]}
    return _known_user_ids


def _upsert_user(user_id: str, display_name: str, source: str) -> None:
    data = _load_users()
    existing = {u["userId"]: i for i, u in enumerate(data["users"])}

    if user_id not in existing:
        data["users"].append({
            "userId": user_id,
            "displayName": display_name,
            "source": source,
            "joinedAt": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("新使用者: %s (%s) via %s", display_name, user_id, source)
    else:
        # 暱稱可能有變，更新
        data["users"][existing[user_id]]["displayName"] = display_name

    _save_users(data)
    if _known_user_ids is not None:
        _known_user_ids.add(user_id)


def _get_display_name(user_id: str, group_id: str | None = None) -> str:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        if group_id:
            url = LINE_GROUP_MEMBER_URL.format(group_id=group_id, user_id=user_id)
        else:
            url = LINE_PROFILE_URL.format(user_id=user_id)
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("displayName", user_id)
    except Exception as e:
        logger.warning("取得暱稱失敗 %s: %s", user_id, e)
        return user_id


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = os.environ.get("LINE_CHANNEL_SECRET", "")
    if not secret:
        logger.warning("LINE_CHANNEL_SECRET 未設定，跳過簽名驗證")
        return True
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    expected = b64decode(signature)
    return hmac.compare_digest(digest, expected)


@app.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: str = Header(...),
) -> dict:
    body = await request.body()

    if not _verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)

    for event in payload.get("events", []):
        event_type = event.get("type")
        source = event.get("source", {})
        group_id = source.get("groupId")

        if event_type == "follow":
            # 使用者追蹤官方帳號
            user_id = source.get("userId")
            if user_id:
                name = _get_display_name(user_id)
                _upsert_user(user_id, name, source="follow")

        elif event_type == "memberJoined":
            # 使用者加入群組
            for member in event.get("joined", {}).get("members", []):
                if member.get("type") == "user":
                    user_id = member["userId"]
                    name = _get_display_name(user_id, group_id=group_id)
                    _upsert_user(user_id, name, source="group_join")

        elif event_type == "message":
            # 有人在群組發訊息，若不在名單內才補入
            user_id = source.get("userId")
            if user_id and group_id and user_id not in _get_known_ids():
                name = _get_display_name(user_id, group_id=group_id)
                _upsert_user(user_id, name, source="message")

        elif event_type == "join":
            # Official Account 被加入群組，印出 groupId 方便設定
            if group_id:
                logger.info("Official Account 已加入群組，Group ID: %s", group_id)

    return {"status": "ok"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}