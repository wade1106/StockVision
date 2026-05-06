"""
後端伺服器啟動腳本：LINE Webhook + JSON API 合併在同一個 FastAPI app。
搭配 Cloudflare Tunnel 對外暴露本機端點。

執行方式：
  uv run python scripts/webhook_server.py

Cloudflare Tunnel（另開一個終端機）：
  cloudflared tunnel --url http://localhost:8000

前端開發（另開一個終端機）：
  cd web && npm run dev
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

import uvicorn
from src.notify.webhook import app
from src.web.app import app as web_app

# 將 web API routes 掛入 webhook app
for route in web_app.routes:
    app.routes.append(route)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
