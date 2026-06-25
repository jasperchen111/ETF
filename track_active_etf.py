"""
台股主動式ETF 每日持股追蹤
資料來源：MoneyDJ理財網 (公開頁面，每個ETF依投信每日公告之持股組合更新)
功能：
  1. 抓取設定清單中每檔主動式ETF的「前10大持股」
  2. 跟上一次抓到的快照比對，找出新增/出清/加碼/減碼的股票
  3. 把結果整理成一份「每日報」文字，發送到 Telegram
  4. 把這次抓到的資料存成快照，供下一次比對使用（由GitHub Actions自動commit回repo）

使用前請先設定環境變數：
  TELEGRAM_BOT_TOKEN  - 你的Telegram Bot Token
  TELEGRAM_CHAT_ID    - 你要接收通知的聊天室ID
"""

import os
import re
import json
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ---------- 設定：要追蹤的主動式ETF ----------
ETF_LIST = {
    "00981A": "主動統一台股增長",
    "00991A": "主動復華未來50",
    "00994A": "主動第一金台股優",
    "00995A": "主動中信台灣卓越",
    "00992A": "主動群益科技創新",
}

DATA_DIR = "data"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_holdings(etf_code: str):
    """抓取單一ETF的前10大持股，回傳 (資料日期字串, {股票代號: {"name":..,"shares":..}})"""
    url = f"https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid={etf_code}.TW"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    # 頁面上「持股分佈(依產業)」跟「持股明細」各自標了一個資料日期，
    # 我們要的是「持股明細」旁邊那組，所以先定位到「持股明細」之後再找日期
    page_text = soup.get_text()
    detail_idx = page_text.find("持股明細")
    search_scope = page_text[detail_idx:] if detail_idx != -1 else page_text
    date_match = re.search(r"資料日期[:：]\s*(\d{4}/\d{2}/\d{2})", search_scope)
    data_date = date_match.group(1) if date_match else "未知日期"

    holdings = {}
    for table in soup.find_all("table"):
        header_text = table.get_text()
        if "個股名稱" in header_text and "持有股數" in header_text:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                name_cell_text = cells[0].get_text(strip=True)
                m = re.match(r"^(.*?)\(([\w\*]+)\.TW\)", name_cell_text)
                if not m:
                    continue
                stock_name, stock_code = m.group(1), m.group(2)
                shares_text = cells[2].get_text(strip=True).replace(",", "")
                try:
                    shares = int(float(shares_text))
                except ValueError:
                    continue
                holdings[stock_code] = {"name": stock_name, "shares": shares}
            break
    return data_date, holdings


def load_previous_snapshot(etf_code: str):
    path = os.path.join(DATA_DIR, f"{etf_code}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(etf_code: str, data_date: str, holdings: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{etf_code}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": data_date, "holdings": holdings}, f, ensure_ascii=False, indent=2)


def diff_holdings(prev_holdings: dict, curr_holdings: dict):
    """回傳 (新增清單, 出清清單, 增減清單[股票代號,股票名稱,張數變化])"""
    new_stocks = []
    removed_stocks = []
    changed = []

    for code, info in curr_holdings.items():
        if code not in prev_holdings:
            new_stocks.append((code, info["name"], info["shares"] / 1000))
        else:
            old_shares = prev_holdings[code]["shares"]
            if old_shares != info["shares"]:
                lot_change = (info["shares"] - old_shares) / 1000
                changed.append((code, info["name"], lot_change))

    for code, info in prev_holdings.items():
        if code not in curr_holdings:
            removed_stocks.append((code, info["name"], info["shares"] / 1000))

    return new_stocks, removed_stocks, changed


def build_etf_report(etf_code: str, etf_name: str):
    data_date, curr_holdings = fetch_holdings(etf_code)
    prev_snapshot = load_previous_snapshot(etf_code)

    lines = [f"【{etf_name}（{etf_code}）】資料日期：{data_date}"]

    if prev_snapshot is None:
        lines.append("→ 第一次抓取，已建立基準快取，明天開始比對變化。")
    elif prev_snapshot.get("date") == data_date:
        lines.append("→ 投信尚未公布新資料，維持前次持股不變。")
    else:
        new_stocks, removed_stocks, changed = diff_holdings(
            prev_snapshot.get("holdings", {}), curr_holdings
        )
        if not new_stocks and not removed_stocks and not changed:
            lines.append("→ 前10大持股無變化。")
        else:
            for code, name, lots in new_stocks:
                lines.append(f"🆕 新增 {name}({code})，{lots:.0f} 張")
            for code, name, lots in removed_stocks:
                lines.append(f"❌ 出清 {name}({code})，原持有 {lots:.0f} 張")
            for code, name, lot_change in changed:
                arrow = "🔺加碼" if lot_change > 0 else "🔻減碼"
                lines.append(f"{arrow} {name}({code}) {lot_change:+.0f} 張")

    save_snapshot(etf_code, data_date, curr_holdings)
    return "\n".join(lines)


def send_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，僅印出報告：\n")
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram 單則訊息上限約4096字，超長就切段送出
    max_len = 3500
    for i in range(0, len(message), max_len):
        chunk = message[i:i + max_len]
        resp = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=20)
        if resp.status_code != 200:
            print(f"Telegram發送失敗：{resp.status_code} {resp.text}", file=sys.stderr)


def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_sections = [f"📊 主動式ETF 每日持股報告（{today_str}）\n"]

    for code, name in ETF_LIST.items():
        try:
            section = build_etf_report(code, name)
        except Exception as e:
            section = f"【{name}（{code}）】抓取失敗：{e}"
        report_sections.append(section)

    full_report = "\n\n".join(report_sections)
    send_telegram(full_report)


if __name__ == "__main__":
    main()
