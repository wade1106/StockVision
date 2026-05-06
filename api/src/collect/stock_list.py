import logging
import time
from io import StringIO

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TWSE_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
TPEX_URL = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _parse_isin_page(url: str, retries: int = 3, backoff: float = 2.0) -> pd.DataFrame:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            session = requests.Session()
            resp = session.get(url, headers=HEADERS, timeout=30, verify=False)
            break
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                logger.warning("第 %d 次連線失敗，%.1f 秒後重試: %s", attempt, backoff, exc)
                time.sleep(backoff)
                backoff *= 2
    else:
        raise last_exc  # type: ignore[misc]

    resp.encoding = "big5"
    resp.encoding = "big5"
    
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", {"class": "h4"}) # 證交所這頁的核心表格通常有 class='h4'
    
    if not table:
        # 如果找不到 class='h4'，抓頁面中唯一的那個大表格
        table = soup.find("table")
        
    if not table:
        logger.error(f"無法在頁面中找到任何表格: {url}")
        return pd.DataFrame()

    data = []
    rows = table.find_all("tr")
    
    for row in rows:
        cols = row.find_all("td")
        cols = [ele.text.strip() for ele in cols]
        if len(cols) > 0:
            data.append(cols)

    if not data:
        return pd.DataFrame()

    # 轉換成 DataFrame
    df = pd.DataFrame(data)
    
    # 尋找標題列（包含 '有價證券別' 或 '有價證券代號及名稱' 的那一列）
    header_idx = None
    for i, row in enumerate(data):
        if "有價證券別" in row or "有價證券代號及名稱" in row:
            header_idx = i
            break

    if header_idx is None:
        logger.error(f"找不到標題列，抓到的第一行資料為: {data[0] if data else 'Empty'}")
        return pd.DataFrame()

    # 設定標題並過濾
    df.columns = df.iloc[header_idx]
    df = df.iloc[header_idx + 1:].reset_index(drop=True)
    
    # 只留股票
    if "有價證券別" in df.columns:
        df = df[df["有價證券別"] == "股票"].copy()
    
    if "有價證券代號及名稱" in df.columns:
        df = df[["有價證券代號及名稱", "市場別"]].copy()
        df.columns = ["code_name", "market"]
        
        # 拆分 代號 與 名稱
        split = df["code_name"].str.extract(r"^(\d{4,6})\s+(.+)$")
        df["code"] = split[0]
        df["name"] = split[1]
        
        return df.dropna(subset=["code", "name"])[["code", "name", "market"]].reset_index(drop=True)

    return pd.DataFrame()


def get_all_stocks() -> pd.DataFrame:
    """
    回傳台股全市場股票清單（上市 + 上櫃），欄位：code, name, market, ticker
    ticker 格式為 yfinance 使用的 <code>.TW / <code>.TWO
    """
    dfs = []
    try:
        twse = _parse_isin_page(TWSE_URL)
        twse["ticker"] = twse["code"] + ".TW"
        dfs.append(twse)
        logger.info("TWSE 上市: %d 支", len(twse))
    except Exception as e:
        logger.error("TWSE 股票清單抓取失敗: %s", e)

    try:
        tpex = _parse_isin_page(TPEX_URL)
        tpex["ticker"] = tpex["code"] + ".TWO"
        dfs.append(tpex)
        logger.info("TPEX 上櫃: %d 支", len(tpex))
    except Exception as e:
        logger.error("TPEX 股票清單抓取失敗: %s", e)

    if not dfs:
        raise RuntimeError("無法取得任何股票清單")

    result = pd.concat(dfs, ignore_index=True)
    logger.info("全市場合計: %d 支", len(result))
    return result
