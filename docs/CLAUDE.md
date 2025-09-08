# 台股 N 字回撤掃描器 — 專案說明（claude.md）

> 目標：用 **Claude Code** 寫出一套「**台股（上市＋上櫃）N 字回撤**」掃描工具，**資料免費且可行**、**只納入股票（排除 ETF/ETN/權證/DR/債/特別股/興櫃）**、**全市場掃描 ≤ 3 分鐘**，並提供可用的前後端串聯與驗證機制。

---

## 1) 核心需求（從使用者故事展開）

1. **作為量化/技術分析者**，我需要每天在收盤後，**掃描臺股（上市＋上櫃）的全部普通股**，找出符合 **N 字回撤** 規則的標的。
2. **作為工程實作者**，我需要**完全免費**的數據來源與**穩定的 API/CSV**，可**批次取回**全市場當日 OHLC，並能**回補歷史**。
3. **作為產品使用者**，我希望有**前端頁面**可查看「掃描清單＋個股明細（K 線、切腳點、參數）」並可**調參**（回撤比例、最小波幅、確認條件…）。
4. **作為維運者**，我需要**數量校驗**（上市/上櫃股票數是否吻合官方名單）、**資料品質檢查**、**快取與重試策略**、**每日自動化排程**。

**成功標準（Acceptance Criteria）**

* **資料來源：** 僅使用**免費**官方或開源來源；可 **回補 ≥ 3 年日 K**；每日 **T+0（收盤後）** 更新。
* **掃描效能：** 全市場（上市＋上櫃普通股）**≤ 3 分鐘**（含讀檔與演算法判斷，不含首次回補）。
* **正確性：** 股票範圍**不含** ETF、ETN、權證、DR、債、特別股、興櫃；**上市＋上櫃數量**與官方名單**日更比對**；掃描結果可**重現**。
* **可用性：** 提供 **REST API** 與 **前端頁面**；可調整 **N 字回撤**參數；可下載**結果 CSV**。

---

## 2) 數據源（免費＆可行）

### 2.1 證券清單（確保「股票」範圍與數量）

* **TWSE 上市 ISIN 名單**（`strMode=2`）→ 解析「有價證券種類＝股票」＋市場別＝上市。
* **TPEx 上櫃 ISIN/名單**（`strMode=4` 或 TPEx 名單頁）→ 解析「股票」＋市場別＝上櫃。
* **處理邏輯**：

  * 僅納入「**普通股**」。排除：ETF、ETN、受益憑證、存託憑證（DR）、認購(售)權證、公司債、特別股、興櫃（含創新板）。
  * 以 **ISIN 名單為主檔**（每天抓取/版控）；加入欄位：`market`（TWSE/TPEx）、`type`（stock/etf/...）、`status`（normal/suspended/delisted）。

### 2.2 當日盤後 **全市場 OHLC**（減少大量逐檔請求）

* **TWSE（上市）**：每日**整批盤後**個股行情（`MI_INDEX` 類報表，可取到當日所有上市普通股之 **開高低收/量**）。
* **TPEx（上櫃）**：**Daily Close Quotes** 提供**可下載 CSV** 的全市場盤後個股行情（含 OHLC/量）。
* **清洗重點**：去千分位逗號、轉數值、處理 `—` 空值、停牌個股。

### 2.3 歷史回補（首次建庫＋週期性補洞）

* **首選：TWSE 個股日 K**（`STOCK_DAY`，逐檔月分段 JSON/CSV）＋ **TPEx** 個股歷史頁的 CSV（必要時）。
* **替代/加速：FinMind `TaiwanStockPrice`**（免費、需 token 才能拉高限額；作為**回補與日更的備援**）。
* **調整權益處理**：策略以**未復權**或**前復權**擇一為基準（推薦「前復權」以避免除權息跳空造成形態誤判）。若採 FinMind，可直接使用其已處理欄位；若用官方原始價，需用股利/拆併資訊自行轉換（可後續擴充）。

> **落地原則**：**每日增量**抓兩份「整批盤後」資料（上市 1 份、上櫃 1 份）＋合併進本地 **Parquet**，**演算法只掃當日與近 N 日歷史**，將**網路 I/O** 壓到最低。

---

## 3) 股票範圍與數量校驗（嚴格過濾非股票）

**流程**

1. 下載/解析 **TWSE 上市 ISIN（strMode=2）**、**TPEx 上櫃 ISIN（strMode=4）**。
2. 過濾 `security_type == 股票` 且 `market ∈ {TWSE, TPEx}`。
3. 排除 `name` 或 `category` 含：ETF、ETN、受益憑證、權證、DR、公司債、特別股、興櫃…（雙保險：**白名單＝普通股**、**黑名單＝各類衍生/基金/債**）。
4. 生成 **universe.csv**（欄位：`stock_id`, `isin`, `name`, `market`, `listed_date`, `status`）。
5. **每日校驗**：將 universe 與當日盤後整批清單**雙向比對**（缺漏/新增/下市），若**數量不吻合→告警**。

> **輸出**：`universe_count_{yyyy-mm-dd}.json`（twse\_count、tpex\_count、total、diff、new\_listings、delisted）。

---

## 4) **N 字回撤** 指標（最終規格）

> 依你提供的定義完成參數化規格、計算公式與入選條件；演算法以 ABC 形態為核心，並在後續交易日根據三項觸發條件擇一成立即入選。

### 4.1 名詞與形態判定（多頭 N）

* **A**：近期明確低點（起漲點）。
* **B**：A 後的波段高點（上漲至少達到「最小漲幅」）。
* **C**：自 B 回撤後的低點，且 **C 高於 A**（可設容差）。
* **N 形態成立條件**：

  1. `rise_pct = (B - A) / A ≥ min_leg_pct`
  2. `retr_pct = (B - C) / (B - A) ∈ [retr_min, retr_max]`（預設 0.30\~0.70）
  3. `C ≥ A × (1 - c_tol)`（預設 `c_tol = 0`）

> 備註：空頭 N（反向）可同理擴充，但本專案先實作多頭。

### 4.2 回撤比率公式

```
回撤比率 retr_pct = (B_price - C_price) / (B_price - A_price)
```

* 回撤 50% 最理想；30%\~70% 視為健康回撤區。

**範例（融程電）**

* A=165.30、B=245.80、C=192.50 ⇒ `retr_pct = (245.80-192.50) / (245.80-165.30) = 53.30 / 80.50 ≈ 0.662`（回撤 66.2%）。

### 4.3 量能比（VR20）

```
量能比 volume_ratio = 今日成交量 / 過去 20 日平均量
```

* 3.0 以上=爆量；2.0 以上=大量；1.5 以上=放量；1.2 以下=縮量。

### 4.4 觸發條件（擇一成立即入選）

* **條件1：突破昨高** → `close_t > high_{t-1}`
* **條件2：量增上穿 EMA5** → `close_t > EMA5_t 且 volume_ratio_t > 1.0`
* **條件3：RSI 強勢** → `RSI14_t ≥ 50`

> 只要 **ABC 形態成立** 且 **三項條件至少一項為真**，記錄為當日訊號。

### 4.5 綜合評分（0\~100 分）

1. **回撤深度分 40%**：距 0.5 越近分越高（對稱懲罰 0 與 1）。
2. **量能比分 25%**：`volume_ratio` 線性/對數映射上限（建議 3.0 封頂）。
3. **反彈早期分 15%**：C 到當日 bars 數越少分越高（鼓勵早進）。
4. **均線多頭分 10%**：`close ≥ EMA5/EMA20` 分段加分（各 5 分）。
5. **健康度分 10%**：`RSI14 ∈ [50,70]` 加分，過熱（>75）或轉弱（<50）扣分；單日漲幅過大（如 >9%）酌扣以控風險。

> 最終 `score = round(sum(weighted_components))`；並回傳 `score_breakdown` 供前端顯示。

### 4.6 演算法流程

1. **切腳偵測**：用 **ZigZag**（以 `min_leg_pct` 或 `ATR*k`）在近 `lookback_bars`（預設 200）找 HLHL… 轉折。
2. **尋找最後一組 ABC**：滿足 4.1 的三項條件，且 C 時點為**最近**的一個合規回撤低點。
3. **今日觸發判斷**：在 `t ≥ C_date` 的交易日，檢查 4.4 三條件是否任一成立。
4. **計分**：依 4.5 計算 `score` 與分項。
5. **輸出**：當日訊號（含 A/B/C 價位、日期、`rise_pct/retr_pct/bars_ab/bars_bc/bars_c_to_t/volume_ratio/EMA5/RSI14/score/flags`）。

### 4.7 指標實作細節

* **EMA5**：`EMA_t = α*close_t + (1-α)*EMA_{t-1}`，`α = 2/(N+1)`，N=5。
* **RSI14（Wilder）**：

  * 初始 `avg_gain_14/avg_loss_14` 取 14 日均值；後續採 Wilder 平滑。
  * `RS = avg_gain/avg_loss`，`RSI = 100 - 100/(1+RS)`。
* **量能比**：20 日簡單均量；停牌/零量以 `NaN` 排除計算母集合。
* **昨高**：以同一復權邏輯的 `high_{t-1}`。
* **復權**：全計算流程以**前復權價**為主，避免權益調整造成假突破/假回撤。

### 4.8 參數預設（可於前端調整）

* `lookback_bars = 200`
* `min_leg_pct = 0.10` **或** `atr_k = 3.0`（二擇一）
* `retr_min = 0.30`、`retr_max = 0.70`
* `c_tol = 0.00`（C 不可破 A；可設 0.5% 彈性）
* `ema_len = 5`、`rsi_len = 14`、`vol_ma_len = 20`
* `vol_cap_for_score = 3.0`（量比分上限）
* `cooldown_days = 20`（同檔重複訊號間隔）

### 4.9 偽代碼（Polars/Python）

```python
# df: [date, open, high, low, close, volume]
zig = zigzag(df, threshold=min_leg_pct or atr_k)
A,B,C = find_last_abc(zig, retr_min, retr_max, c_tol)
if A and B and C:
    ema5 = ema(df.close, 5)
    rsi14 = rsi_wilder(df.close, 14)
    vol_ratio = df.volume[-1] / sma(df.volume, 20)[-1]
    cond1 = df.close[-1] > df.high[-2]
    cond2 = (df.close[-1] > ema5[-1]) and (vol_ratio > 1.0)
    cond3 = rsi14[-1] >= 50
    if cond1 or cond2 or cond3:
        score = score_components(retr_pct(A,B,C), vol_ratio, bars_since(C), ema5[-1], sma(df.close,20)[-1], rsi14[-1])
        emit_signal(...)
```

---

## 5) 系統架構與串聯（後端 × 前端）

### 5.1 後端（建議 Python + FastAPI / Polars）

* **資料層**：

  * `data/universe/{date}.parquet`（上市/上櫃普通股清單）
  * `data/daily/{yyyy-mm-dd}/twse.parquet`、`tpex.parquet`（當日整批盤後）
  * `data/history/{stock_id}.parquet`（回補後之日 K；滾動更新）
* **服務層**：

  * `GET /health`
  * `GET /universe?date=yyyy-mm-dd` → 驗證與下載
  * `GET /scan?date=yyyy-mm-dd&params=...` → 產出 N 字回撤清單（JSON）
  * `GET /stock/{id}/bars?start=yyyy-mm-dd` → 個股日 K（前端畫 K 線）
  * `GET /export/scan.csv?date=...` → 下載結果 CSV
* **排程**：`cron 16:00 Asia/Taipei`（遇假日自動略過），流程：更新 **universe** → 下載 **twse+tpex 當日盤後** → 合併入庫 → 執行 **scan** → 產出報表＋快取。

### 5.2 前端（建議 Svelte/React 任一；簡潔高效）

* **首頁**：

  * 參數面板：`lookback_bars`、`min_leg_pct/atr_k`、`retracement_min/max`、`confirm_break_b`、`volume_filter`…
  * 結果表格：`stock_id`、`name`、`market`、`signal_date`、`A/B/C/D`、`retr_pct`、`rise_pct`、`score`、`link`（跳明細）。
* **明細頁**：

  * K 線（最近 250 根）＋ A/B/C/D 標註＋量能；
  * 規則落點與參數摘要；
  * 下載按鈕（CSV / 圖片）。
* **串聯**：純 **REST**（CORS 開啟）；前端只消費 JSON，不直接打外部資料源。

---

## 6) 效能與穩定性（≤ 3 分鐘達標）

* **資料取得**：每日只有 **2 次 HTTP**（上市整批＋上櫃 CSV 整批），**O(1)** 級別，網路 I/O 最小化。
* **計算**：全市場 \~1,800 檔 × 250 根日 K ≈ **45 萬列**；以 **Polars Lazy**、向量化與 **並行**（多進程/多執行緒）處理，常規環境可在 **< 1 分鐘** 完成（演算法層）。
* **快取**：將近 30\~60 天的日 K 以 **columnar（Parquet/Feather）** 格式快取；掃描僅載入必要欄位（`high/low/close/volume`）。
* **重試**：網路逾時/500 → **退避重試**；資料缺漏 → 與\*\*備援源（FinMind）\*\*合併（以官方為主）。

---

## 7) 資料清洗與異常

* **千分位/破折號** → 去除/補 `NaN`；
* **停牌/無成交** → 當日 `close`/`volume` 缺值者標示 `suspended=True`；
* **除權息/拆併** → 採一種標準價（建議「前復權」）以避免誤判；
* **新上市/下市** → `universe` 日更自動增刪；
* **交易日曆** → 以官方行事曆表（可自建）避免非交易日誤觸；
* **時區** → `Asia/Taipei` 一致化。

---

## 8) 測試計畫

* **單元測試**：切腳偵測、回撤計算、突破確認、數據清洗。
* **整合測試**：每日排程→掃描→前端渲染；
* **回溯測試**：取近 3 年資料，隨機抽 50 檔人工核對；
* **效能測試**：在常規筆電/雲上測 **N=3** 次，平均時間 **≤ 3 分鐘**。

---

## 9) 交付物

* `ingest/`：資料抓取與清洗（TWSE/TPEx/FinMind 備援）。
* `store/`：Parquet/Feather 快取與合併邏輯。
* `signal/`：N 字回撤偵測模組（可調參）。
* `api/`：FastAPI 服務（OpenAPI/Swagger）。
* `web/`：前端頁面（參數面板＋列表＋明細 K 線）。
* `ops/`：排程腳本、告警（數量不符/資料缺漏/掃描超時）。
* `docs/`：README＋部署手冊＋指標說明＋參數說明。

---

## 10) 風險與應對

* **官網頁面改版** → 以 **選擇器/欄位名白名單** 做解析；備援 FinMind。
* **API 限流** → 日更走整批（2 份檔），回補走**節流**＋**持續化**；
* **權益調整** → 先以規則「相對比例」降低影響，之後再補正式復權流程；
* **誤檢/漏檢** → 加入**可視化標註**與**人工抽樣**流程，定期校正參數。

---

## 11) 後續你需要提供的資訊

1. **N 字回撤的最終定義**（回撤區間、突破條件、是否要量能/均線/型態輔助）。
2. **價型時間窗**（只看日 K？是否另加週 K/60 分 K 佐證）。
3. **輸出欄位順位**（你要放在前端表格的 KPI 欄位）。
4. **效能環境**（你的機器規格 or 執行在雲端？）

> 有了以上（特別是 #1），演算法即可 **零痛點落地**。

---

## 12) 參數建議（預設值，待你改）

* `lookback_bars = 200`
* `min_leg_pct = 0.10`（或 `atr_k = 3.0` 擇一）
* `retracement_min = 0.382`、`retracement_max = 0.618`
* `confirm_break_b = True`（以「收盤突破」為準）
* `volume_filter = True, k = 1.5`
* `cooldown_days = 20`

---

### 附錄 A｜資料表 Schema（建議）

* `universe.parquet`：`[stock_id, isin, name, market, listed_date, status]`
* `daily_ohlcv.parquet`：`[date, stock_id, open, high, low, close, volume, market, adj_flag]`
* `signals.parquet`：`[date, stock_id, A, B, C, D, rise_pct, retr_pct, bars_ab, bars_bc, bars_cd, volume_factor, score]`

### 附錄 B｜前端 JSON 範例

```json
// /scan?date=2025-09-05
{
  "params": {
    "lookback_bars": 200,
    "min_leg_pct": 0.10,
    "retr": [0.30, 0.70],
    "ema_len": 5,
    "rsi_len": 14,
    "vol_ma_len": 20,
    "cooldown_days": 20
  },
  "rows": [
    {
      "stock_id": "2330",
      "name": "台積電",
      "market": "TWSE",
      "signal_date": "2025-09-05",
      "A": 770.0,
      "B": 920.0,
      "C": 860.0,
      "rise_pct": 0.195,
      "retr_pct": 0.500,
      "bars_ab": 18,
      "bars_bc": 7,
      "bars_c_to_t": 3,
      "ema5": 915.2,
      "rsi14": 58.3,
      "volume_ratio": 1.99,
      "triggers": {"break_yh": true, "ema5_vol": true, "rsi_strong": true},
      "score": 87,
      "score_breakdown": {"retr": 34.0, "vol": 21.5, "early": 13.0, "ma": 8.0, "health": 10.5}
    }
  ]
}
```

---

> **備註**：三項觸發任一成立即回報信號；空頭 N 與更進階條件（如多週期驗證、量價結構過濾）可於後續版本擴充。
