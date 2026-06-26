# So sánh Phiên bản — Kairos-v2

Tài liệu này so sánh các phiên bản engine của Kairos: bản **mở** (open, đi kèm repository) và bản **đóng** (closed / high, dành cho cấp phép).

**Mục tiêu:** Giúp bạn chọn bản phù hợp với nhu cầu.

**Số liệu:** Đo trực tiếp từ source code (số file, số dòng, số hàm `pt_*`) tại thời điểm cập nhật. Hiệu năng tuyệt đối phụ thuộc dataset và phần cứng — các nhận định ở đây là **định tính + quy mô code**.

**Lưu ý:** Tài liệu KHÔNG mô tả thuật toán nội bộ của bản đóng — chỉ nêu khả năng, input/output, hành vi và use case.

---

## Chọn bản nào? (tóm tắt)

| Nhu cầu | Bản phù hợp | Lý do |
|--------|-----------|------|
| Học tập, PoC, thử logic | Open | Mã nguồn công khai, pipeline hoàn chỉnh |
| Nghiên cứu production-ready | Open | 68 indicators, Optuna + walk-forward + DSR guardrails |
| Cần chỉ báo HTF **live trong nến** (intrabar) | High 🔒 | Đặc quyền live MTF của bản đóng |

> **Kết luận thẳng thắn:** Tại bản hiện tại, bản **open** đã ngang bằng bản **high** về *phổ chỉ báo* (cùng 68), *quy mô code* (~8.4K dòng) và *engine tối ưu* (cùng Optuna, cùng engine backtest 585 dòng). Khác biệt thực sự còn lại **duy nhất** là: chỉ báo khung lớn của bản high **cập nhật live trong nến đang hình thành**, còn bản open **rải nến HTF đã đóng xuống (phẳng)**.

---

## 0. TL;DR

| Engine | Bản | Mã nguồn | Quy mô (đo thực tế) | Định vị |
|---|---|:---:|:---:|---|
| **Indicator** | `Indicator/` | 🔓 Mở | **8,405 dòng · 68 `pt_*`** | Nền tảng công khai — HTF **phẳng** (rải nến đã đóng) |
| **Indicator** | `Indicator_high` | 🔒 Đóng | 8,412 dòng · 68 `pt_*` | Production — **live MTF intrabar** + tối ưu độ sâu tín hiệu |
| **Optimizer** | `toi_uu_hoa/` | 🔓 Mở | **3,924 dòng** | Optuna (Bayesian) + walk-forward + DSR guardrails |
| **Optimizer** | `toi_uu_hoa_high` | 🔒 Đóng | 3,924 dòng | Bản thương mại — **chung engine** với bản open |

**Một câu:** bản **mở** đủ để chạy toàn bộ pipeline end-to-end, full indicator breadth (68), và tối ưu tham số nghiêm túc (Optuna + walk-forward + DSR); bản **đóng** thêm đúng một thứ đáng kể về mặt hành vi: *cập nhật chỉ báo HTF **live** trong nến*.

---

## 1. Bản đồ phiên bản

```text
Indicator (Feature Engine)              Optimizer (Tối ưu tham số)
├── Indicator/        🔓  open / base    ├── toi_uu_hoa/       🔓  open
└── Indicator_high    🔒  high (closed)  └── toi_uu_hoa_high   🔒  high (closed)
```

> Bản đóng (`Indicator_high`, `toi_uu_hoa_high`) **không nằm trong repository công khai** — chúng được giữ riêng (gitignore) cho mục đích cấp phép/thương mại. **Không có** bản `Indicator_mid` (đã bỏ).

Cùng một **giao diện hàm** (`pt_*` cho chỉ báo; `run_*_optimization` cho optimizer) → các bản **thay thế nhau được** mà không phải sửa pipeline. Nâng cấp = đổi thư mục import, không đổi kiến trúc.

---

## 2. Engine Indicator — open vs high

### 2.1 Quy mô (đo thực tế)

| Chỉ số | `Indicator/` (open 🔓) | `Indicator_high` (🔒 — tham chiếu) |
|---|:---:|:---:|
| Số file `.py` | 7 | 7 |
| **Tổng dòng code** | **8,405** | 8,412 |
| **Số hàm chỉ báo** (`pt_*`) | **68** | **68** |
| Tổng số hàm (`def`) | 109 | ~109 |
| Quy mô tương đối | **1.0x** | **~1.0x** (ngang nhau) |

> **Thực tế:** Bản open và bản high hiện **ngang nhau về phổ và quy mô** (cùng 68 `pt_*`, chênh lệch dòng code không đáng kể). Khác biệt nằm ở **cách xử lý đa khung** (xem §2.3), không phải số lượng chỉ báo.

### 2.2 Chi tiết theo module (số dòng — bản open)

| Module | Open (hiện tại) | Số `pt_*` | Ý nghĩa nhóm chỉ báo |
|---|:---:|:---:|---|
| `xu_huong.py` | 2,052 | 14 | Xu hướng (EMA/SMA/ADX/Ichimoku/SuperTrend/PSAR/Aroon/Vortex/HMA/KAMA/TRIX/ALMA/VWMA) |
| `dong_luong_dao_chieu.py` | 1,787 | 15 | Động lượng & đảo chiều (RSI/Stoch/CCI/Williams %R/ROC/MFI/AO/TSI/Ultimate/StochRSI/CMO/Fisher/STC/RVI) |
| `cau_truc_gia.py` | 1,766 | 11 | Cấu trúc giá (Breakout/ZigZag/Fractals/Pivot/FVG/Heikin Ashi/Market Structure/Order Block/S-R/LinReg/Key Level) |
| `bien_dong.py` | 1,288 | 11 | Biến động (ATR/BB Squeeze/Keltner/Donchian/HistVol/Chaikin Vol/ATR Bands/Chandelier/Choppiness/Fractal Dim/Shannon Entropy) |
| `khoi_luong.py` | 1,130 | 11 | Khối lượng (Volume/Volume MA/OBV/VWAP/Volume Profile/CMF/A-D/MFI Vol/EoM/PVT/Chaikin Osc) |
| `vi_the.py` | 251 | 2 | Vị thế/sentiment (CVD-based position, Elder Ray) |
| `chu_ky.py` | 131 | 4 | Phiên & chu kỳ (kiểm tra ngày/giờ, phiên Á/Âu/Mỹ, session range) |
| **Tổng** | **8,405** | **68** | |

### 2.3 Khác biệt chức năng (điểm cốt lõi free vs premium)

| Khía cạnh | Bản open 🔓 | Bản high 🔒 |
|---|---|---|
| **Phổ (breadth)** | 68 `pt_*` | 68 `pt_*` — **bằng nhau** |
| **Đa khung HTF** | Chỉ báo khung lớn tính trên **nến HTF đã đóng** rồi **rải (forward-fill) xuống** trục 1m → **phẳng** trong mỗi cửa sổ, an toàn look-ahead | Chỉ báo khung lớn **cập nhật live trong nến đang hình thành** → phản ứng sớm, độ phân giải intrabar cao hơn |
| **Độ sâu feature** | Đầy đủ cho nghiên cứu/PoC/production | Tối ưu sâu thêm ở một số chỉ báo (closed-source) |

> Đây là ranh giới free–premium thực sự: **base = HTF confirmed/flat, high = HTF live intrabar.** Mọi khác biệt còn lại (số chỉ báo, quy mô code) hiện **không đáng kể**.

### 2.4 Về True Intrabar

Dù bản `high` hỗ trợ HTF Live/Intrabar, thư viện **không** cố triển khai True Intrabar tuyệt đối cho mọi indicator.

Lý do: một số indicator có công thức đệ quy (recursive state) hoặc phụ thuộc nhiều trạng thái lịch sử của nến HTF đang hình thành. Để đạt True Intrabar 100%, hệ thống phải liên tục dựng lại chuỗi HTF trung gian — tăng đáng kể chi phí tính toán và độ phức tạp.

Thay vào đó, dự án ưu tiên cân bằng giữa:

* Độ chính xác thực tế trong giao dịch.
* Hiệu năng trên tập dữ liệu lớn.
* Khả năng mở rộng cho hàng trăm indicator.

Với phần lớn indicator (RSI, EMA, ROC, Momentum, MACD, Stochastic, RVI...), sai khác giữa HTF Live và True Intrabar thường rất nhỏ. Nhưng với một số indicator phụ thuộc mạnh vào High/Low hoặc trạng thái nội bộ phức tạp, độ lệch có thể lớn hơn, ví dụ:

* ATR · ADX / DMI · SuperTrend · Ichimoku · Donchian Channel
* Một số biến thể Volatility Breakout / Trend-Following dùng High/Low HTF

Vì vậy:

* **HTF Live** phù hợp cho realtime, AI feature engineering, tín hiệu phản ứng sớm.
* **HTF Confirmed (flat)** phù hợp để xác nhận tín hiệu sau khi nến HTF đóng.
* Với chiến lược nhạy cảm High/Low HTF, nên backtest **bar-by-bar trên 1m gốc** để đánh giá chính xác hành vi realtime.

### 2.5 Nên dùng bản nào

| Tình huống | Bản phù hợp |
|---|---|
| Học tập, đọc hiểu, chạy pipeline end-to-end, PoC | `Indicator/` 🔓 |
| Nghiên cứu production, đa symbol, full breadth | `Indicator/` 🔓 (đã đủ lực) |
| Cần tín hiệu HTF **live trong nến** (intrabar) | `Indicator_high` 🔒 |

### 2.6 Ví dụ dữ liệu output — RSI khung 1m & 5m

Mỗi hàm chỉ báo **nhận** một DataFrame OHLCV 1m và **trả lại chính DataFrame đó kèm cột mới**:

| Lời gọi | Cột thêm vào | Thang giá trị |
|---|---|---|
| `pt_rsi(df, "1m", window=14)` | `rsi_1m` | 0–100 |
| `pt_rsi(df, "5m", window=14)` | `rsi_5m` | 0–100 |

> Cả `rsi_1m` lẫn `rsi_5m` gắn vào **cùng một trục thời gian 1m** (mỗi dòng = 1 nến 1m). Khung cao hơn (5m) ở **bản open** được tính **trên nến 5m đã đóng rồi rải (forward-fill) xuống** từng nến 1m — **phẳng** trong mỗi cửa sổ 5m, chống look-ahead. Bản `high` thì cập nhật **live** từng phút.

#### ① `rsi_1m` — GIỐNG nhau ở cả 2 bản

Phép tính gốc trên nến 1m, **không có xử lý đa khung** → không có chỗ để khác nhau.

| time | open 🔓 | high 🔒 |
|---|---:|---:|
| 10:20 | 44.18 | 44.18 |
| 10:23 | 40.93 | 40.93 |
| 10:26 | 34.55 | 34.55 |
| 10:29 | 55.09 | 55.09 |

→ Kiểm tra toàn bộ nến: `open == high` ✅ (trùng tới sai số 1e-9).

#### ② `rsi_5m` — KHÁC nhau theo bản

Khung 5m phải *dựng nến đa khung* từ dữ liệu 1m, và mỗi bản dựng khác nhau:

| Time  | RSI_5m_open | RSI_5m_high |
| :---- | --------: | --------: |
| 10:00 |        60 |        55 |
| 10:01 |        60 |        56 |
| 10:02 |        60 |        57 |
| 10:03 |        60 |        58 |
| 10:04 |        60 |        60 |
| 10:05 |        70 |        60 |
| 10:06 |        70 |        63 |
| 10:07 |        70 |        66 |
| 10:08 |        70 |        68 |
| 10:09 |        70 |        70 |
| 10:10 |        50 |        70 |

**Đọc bảng 5m:**

- **`open` — PHẲNG theo nến 5m đã đóng:** giá trị đứng yên trong mỗi cửa sổ 5 phút (60 cho 10:00–10:04; 70 cho 10:05–10:09…) rồi "nhảy bậc" khi nến 5m mới đóng. Tính ở khung lớn rồi **rải xuống** — **không cập nhật live**, nhẹ và an toàn look-ahead.
- **`high` — LIVE từng phút:** `rsi_5m` cập nhật theo từng nến 1m dựa trên nến 5m đang hình thành (55 → 56 → 57 → … → 70) → phản ứng sớm hơn, độ phân giải trong-nến cao hơn. Đây là **đặc quyền của bản `high`**.

| Bản | Cập nhật trong nến 5m | Đặc tính |
|---|---|---|
| `open` 🔓 | **Phẳng** (rải từ nến đã đóng) | Nhẹ, an toàn look-ahead — bản công khai |
| `high` 🔒 | **Live mỗi phút** | Phản ứng sớm — bản đóng |

> Trên OHLCV thật, **schema/cột và thang giá trị giữ nguyên** — chỉ giá trị thay đổi theo dữ liệu. Quy ước tên `rsi_<khung>` áp dụng cho mọi khung (`rsi_15m`, `rsi_1h`, `rsi_4h`…) và cho cả hai bản.

---

## 3. Engine Optimizer — open vs high

### 3.1 Quy mô (đo thực tế)

| Chỉ số | `toi_uu_hoa/` (open 🔓) | `toi_uu_hoa_high` (🔒 — tham chiếu) |
|---|:---:|:---:|
| Số file `.py` | 10 | 10 |
| **Tổng dòng code** | **3,924** | 3,924 |
| Tổng số hàm (`def`) | 67 | ~67 |
| Coordinator `bo_dieu_phoi.py` | 1,816 dòng | 1,816 dòng |
| Backtest engine `dong_co_backtest.py` | 585 dòng | 585 dòng — **giống hệt** |
| Registry `dang_ky_chi_bao.py` | 145 dòng | ~145 dòng |

### 3.2 Điểm mấu chốt

> **Hai bản optimizer hiện gần như giống hệt nhau.** Cùng 3,924 dòng, cùng engine backtest 585 dòng, và **cả hai đều dùng Optuna** (bộ tối ưu Bayesian/TPE — học từ trial trước, ưu tiên vùng tham số hứa hẹn) trong `bo_dieu_phoi.py`.

| Khía cạnh | `toi_uu_hoa/` (open) | `toi_uu_hoa_high` (closed) |
|---|---|---|
| Thuật toán dò tham số | **Optuna (Bayesian/TPE)** — thích ứng, học từ trial trước | Optuna (Bayesian/TPE) — **chung cơ chế** |
| Walk-Forward IS/OOS | ✅ | ✅ |
| Deflated Sharpe Ratio + hàng rào deploy | ✅ | ✅ |
| Backtest engine | `dong_co_backtest.py` (585 dòng) | **giống hệt** |
| Mã nguồn | 🔓 Mở | 🔒 Đóng (bản thương mại) |

> Khác với tài liệu cũ (vốn cho rằng bản open chỉ "duyệt phẳng/ngẫu nhiên"), **bản open hiện đã dùng Optuna** — cùng lớp thuật toán thích ứng với bản high. Bản `high` hiện là **bản thương mại chung engine**, không có khác biệt thuật toán đáng kể tại thời điểm này.

### 3.3 Đầu vào / Đầu ra (giống nhau giữa 2 bản)

- **Input:** chỉ báo đơn / tổ hợp đa khung (logic AND), khoảng dữ liệu (symbols + ngày), số trials, chỉ số mục tiêu (Sharpe/Sortino…).
- **Output:** bộ tham số + ngưỡng entry/exit tốt nhất (JSON artifact trong `du_lieu/danh_sach_chien_luoc/`) · bảng xếp hạng · báo cáo Walk-Forward IS/OOS · DSR/Sharpe/Sortino · biểu đồ equity/drawdown/PnL.
- **Hàng rào deploy:** DSR ≥ 90% · OOS/IS ≥ 0.8 · OOS Trades ≥ 30 · Profit Factor ≥ 1.2.

### 3.4 Hiệu năng

- **Throughput mỗi trial:** như nhau (chung engine backtest in-memory, chạy hàng nghìn trials không nghẽn I/O).
- **Chất lượng tìm kiếm:** như nhau (cùng Optuna).
- Cả hai đều có thể **dừng giữa chừng** và giữ kết quả tốt nhất hiện có.

### 3.5 Nên dùng bản nào

| Tình huống | Bản phù hợp |
|---|---|
| Mọi nhu cầu dò tham số: walk-forward + DSR, đa khung, quy mô lớn | `toi_uu_hoa/` 🔓 (đã đủ lực) |
| Cần bản đóng gói thương mại / hỗ trợ cấp phép | `toi_uu_hoa_high` 🔒 (liên hệ tác giả) |

---

## 4. Bảng hiệu năng tổng hợp

| Tiêu chí | Indicator open 🔓 | Indicator high 🔒 | Optimizer open 🔓 | Optimizer high 🔒 |
|---|:---:|:---:|:---:|:---:|
| Phổ chỉ báo (`pt_*`) | **68** | **68** | — | — |
| Độ sâu/độ phân giải tín hiệu | ●● | ●● (thêm live) | — | — |
| HTF Live/Confirmed | **Confirmed phẳng** | **Live intrabar** | — | — |
| Thuật toán tối ưu | — | — | Optuna (Bayesian) | Optuna (Bayesian) |
| Tốc độ mỗi trial backtest | — | — | ●● | ●● (giống) |
| Sẵn sàng production | ●● | ●● | ●● | ●● |
| Mã nguồn | Mở 🔓 | Đóng 🔒 | Mở 🔓 | Đóng 🔒 |

> **Chú thích:** ◐ cơ bản · ◑ tốt · ●● mạnh. Định vị tương đối, không phải benchmark tuyệt đối — hãy đo trên dataset & phần cứng của bạn.
>
> **Tóm tắt:** Bản open và high hiện ngang nhau trên hầu hết tiêu chí; khác biệt thực sự còn lại là **HTF Live (high) vs HTF Confirmed/flat (open)**.

---

## 5. Chọn bản nào? (tóm tắt quyết định)

- **Học tập / PoC / kiểm thử logic:** `Indicator/` + `toi_uu_hoa/` (đều mở, full pipeline, dễ sửa).
- **Nghiên cứu chiến lược production-ready, đa symbol, full breadth:** `Indicator/` + `toi_uu_hoa/` (hiện đã đủ lực).
- **Cần live HTF intrabar:** `Indicator_high` (liên hệ tác giả).

> **Ghi chú:** Bản open (`Indicator/` + `toi_uu_hoa/`) trong repo đủ mạnh cho gần như mọi trường hợp nghiên cứu, demo và production. Bản high chỉ thực sự cần khi bạn muốn chỉ báo HTF cập nhật **live trong nến**.

---

## 6. Bản quyền & phạm vi

- Bản **mở** (`Indicator/`, `toi_uu_hoa/`) đi kèm repository, đủ minh hoạ toàn bộ phương pháp luận và chạy end-to-end.
- Bản **đóng** (`Indicator_high`, `toi_uu_hoa_high`): nguyên lý thuật toán, công thức nội bộ và các tối ưu nâng cao được giữ kín (không nằm trong repo công khai). Liên hệ tác giả để biết chi tiết cấp phép.
- **Không có** bản `Indicator_mid` — đã loại bỏ; chỉ còn hai bậc: open (`Indicator/`) và high (`Indicator_high`).

*Xem thêm:* [README → Phiên bản mã nguồn (Editions)](README.md#phiên-bản-mã-nguồn-editions)
