# 主動式ETF 每日持股追蹤機器人

每天自動抓取以下5檔主動式台股ETF的前10大持股，跟前一天比對，
把「新增/出清/加碼/減碼」整理成報告，發到你的Telegram。

預設追蹤清單（在 `track_active_etf.py` 裡的 `ETF_LIST` 可自行增減）：

- 00981A 主動統一台股增長
- 00991A 主動復華未來50
- 00994A 主動第一金台股優
- 00995A 主動中信台灣卓越
- 00992A 主動群益科技創新

資料來源：MoneyDJ理財網的ETF持股公開頁面（投信每個營業日結算淨值後公告，
MoneyDJ會跟著更新，通常會晚個1~2個交易日，這是資料源本身的特性，無法避免）。

---

## 一、建立GitHub repo

1. 到 GitHub 建一個新的repo（public即可，Actions分鐘數無限免費；
   如果想private也行，免費額度通常也夠用）。
2. 把這個資料夾裡的所有檔案上傳上去，目錄結構維持：

```
.github/workflows/daily-report.yml
track_active_etf.py
requirements.txt
data/                  (一開始是空的，程式跑過後會自動產生並commit)
```

---

## 二、設定Telegram通知（取代已停用的LINE Notify）

1. 在Telegram搜尋 `@BotFather`，發送 `/newbot`，依指示取一個機器人名稱，
   完成後它會給你一個 **Bot Token**（長得像 `123456789:ABCdefGhIJK...`）。
2. 用Telegram搜尋你剛建立的Bot名稱，點進去後按「Start」，**隨便發一句話給它**
   （這一步是必要的，不然機器人不知道要回訊息給誰）。
3. 在瀏覽器打開：
   `https://api.telegram.org/bot<你的TOKEN>/getUpdates`
   （把`<你的TOKEN>`換成剛拿到的token）
   會看到一段JSON，裡面找 `"chat":{"id":123456789,...}` ，那個數字就是你的
   **Chat ID**。

---

## 三、把Token跟Chat ID存進GitHub Secrets

1. 進入你的repo → Settings → Secrets and variables → Actions
2. 點「New repository secret」，新增兩個：
   - `TELEGRAM_BOT_TOKEN` → 貼上你的Bot Token
   - `TELEGRAM_CHAT_ID` → 貼上你的Chat ID

---

## 四、測試跑一次

1. 進入repo的「Actions」分頁，左邊選「主動式ETF每日持股追蹤」
2. 點右邊「Run workflow」手動觸發一次
3. 等個1分鐘左右，應該就會收到Telegram訊息了（第一次因為沒有「前一天」
   的資料可以比對，會顯示「已建立基準快取」，這是正常的，從第二次開始
   就會看到實際的進出張數變化）

之後它就會照排程設定（預設平日台灣時間晚上7點）自動執行，不用再手動點。

---

## 想自己調整的地方

- **追蹤哪些ETF**：改 `track_active_etf.py` 裡的 `ETF_LIST`，加代號跟名稱即可。
- **執行時間**：改 `.github/workflows/daily-report.yml` 裡的 `cron`
  （注意cron是UTC時間，台灣時間要 -8小時換算，例如台灣晚上9點 = UTC 13:00 → `0 13 * * 1-5`）。
- **只看前10大持股是因為這是MoneyDJ更新最即時的頁面**；如果你想看完整持股清單，
  可以把程式裡的網址換成 `Basic0007B.xdjhtm`（全部持股），但這個頁面實測
  更新頻率比前10大慢，可能會有資料延遲超過一個月的情況，比較適合偶爾查
  整體配置，不適合做每日比對。

## 免責提醒

這份資料整理純粹是技術上的公開資料追蹤工具，不構成投資建議。ETF的進出張數
反映的是「投信已經做完的操作」，不是預測，請自行評估後再做任何投資決策。
