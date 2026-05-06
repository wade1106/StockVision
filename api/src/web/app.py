import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from src.report.prediction_store import build_comparison
from src.notify.webhook import _get_display_name, _load_users, _save_users

app = FastAPI(title="StockVision API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

USERS_FILE = Path("data/users.json")


@app.get("/api/users")
def get_users() -> dict:
    if not USERS_FILE.exists():
        return {"users": []}
    return json.loads(USERS_FILE.read_text(encoding="utf-8"))


@app.post("/api/users/refresh")
def refresh_users() -> dict:
    """重新從 LINE Profile API 抓取所有成員的顯示名稱。"""
    import os
    group_id = os.environ.get("LINE_GROUP_ID", "") or None
    data = _load_users()
    updated = 0
    for user in data["users"]:
        # 群組成員用 group member API，追蹤者用個人 profile API
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