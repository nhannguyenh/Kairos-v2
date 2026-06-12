"""CẤU TRÚC GIÁ (Market Structure / Price Action)
👉 Thị trường đang ở pha nào?
- Không phải indicator cổ điển, mà là logic
- Higher High / Higher Low
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Support / Resistance
- Supply / Demand
📌 Dùng để:
- Xác định trend thật
- Tránh nhiễu indicator
- Bot chuyên nghiệp luôn có nhóm này"""

import polars as pl


def pt_breakout(df, window=20):
    """Phân tích Price Action bằng Polars: xác định breakout theo đỉnh/đáy n nến trước."""

    df_calc = df.select(
        [
            pl.col("close"),
            pl.col("high").shift(1).rolling_max(window_size=window).alias("high_max"),
            pl.col("low").shift(1).rolling_min(window_size=window).alias("low_min"),
        ]
    )

    # 2. Lấy giá trị của dòng cuối cùng (last row)
    last = df_calc.tail(1).to_dicts()[0]

    close_now = last["close"]
    high_max = last["high_max"]
    low_min = last["low_min"]

    # 3. Logic xác định trạng thái
    # Kiểm tra None để tránh lỗi khi dữ liệu chưa đủ độ dài window
    if high_max is None or low_min is None:
        trang_thai = "KHONG"
    elif close_now > high_max:
        trang_thai = "BREAK_OUT"
    elif close_now < low_min:
        trang_thai = "BREAK_DOWN"
    else:
        trang_thai = "KHONG"

    return {
        "close": close_now,
        "high_max": high_max,
        "low_min": low_min,
        "trang_thai": trang_thai,
    }


def pt_fractals(df, window=2):
    """Phân tích Bill Williams Fractals bằng Polars: Hiệu suất cao."""

    # 1. Tính fractal high/low trên toàn bộ chuỗi (xác nhận sau window nến phải)
    # Fractal high: high[i] > max của window nến mỗi bên
    df_calc = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
            # Fractal high: nến mục tiêu là max trong cửa sổ 2*window+1
            pl.col("high")
            .rolling_max(window_size=2 * window + 1)
            .alias("roll_max_high"),
            pl.col("low").rolling_min(window_size=2 * window + 1).alias("roll_min_low"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    # Tìm fractal đã xác nhận: cần window nến phải để xác nhận -> bỏ window nến cuối
    last_frac_high = None
    last_frac_low = None

    # Duyệt từ đầu đến n-window-1 (đã đủ nến phải để xác nhận)
    confirmed_up_to = n - window - 1
    for i in range(window, confirmed_up_to + 1):
        row = rows[i]
        # Kiểm tra window nến bên trái và bên phải
        center_high = row["high"]
        center_low = row["low"]

        is_frac_high = all(
            rows[i + k]["high"] < center_high for k in range(1, window + 1)
        ) and all(rows[i - k]["high"] < center_high for k in range(1, window + 1))
        is_frac_low = all(
            rows[i + k]["low"] > center_low for k in range(1, window + 1)
        ) and all(rows[i - k]["low"] > center_low for k in range(1, window + 1))

        if is_frac_high:
            last_frac_high = center_high
        if is_frac_low:
            last_frac_low = center_low

    # 2. Lấy giá đóng cửa hiện tại (nến cuối)
    close_now = rows[-1]["close"] if rows else None

    # 3. Xác định trạng thái và mức độ
    if close_now is None or last_frac_high is None or last_frac_low is None:
        return {
            "fractal_high": last_frac_high,
            "fractal_low": last_frac_low,
            "trang_thai": "TRONG_RANGE",
            "muc_do": "YEU",
        }

    if close_now > last_frac_high:
        trang_thai = "BREAKOUT_UP"
    elif close_now < last_frac_low:
        trang_thai = "BREAKOUT_DOWN"
    else:
        trang_thai = "TRONG_RANGE"

    # Mức độ: MANH nếu phá ra rõ ràng (>0.1% ngoài fractal), YEU nếu vừa chạm
    if trang_thai == "BREAKOUT_UP":
        muc_do = "MANH" if close_now > last_frac_high * 1.001 else "YEU"
    elif trang_thai == "BREAKOUT_DOWN":
        muc_do = "MANH" if close_now < last_frac_low * 0.999 else "YEU"
    else:
        muc_do = "YEU"

    return {
        "fractal_high": last_frac_high,
        "fractal_low": last_frac_low,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_pivot_points(df, lookback=5):
    """Phân tích Swing Pivot Points (đỉnh/đáy cục bộ) bằng Polars: Hiệu suất cao."""

    df_calc = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
            pl.col("high").rolling_max(window_size=2 * lookback + 1).alias("roll_max"),
            pl.col("low").rolling_min(window_size=2 * lookback + 1).alias("roll_min"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    # Tìm pivot đã xác nhận: duyệt đến n-lookback-1 (đủ nến phải)
    last_pivot_high = None
    last_pivot_low = None

    confirmed_up_to = n - lookback - 1
    for i in range(lookback, confirmed_up_to + 1):
        center_high = rows[i]["high"]
        center_low = rows[i]["low"]

        is_pivot_high = all(
            rows[i + k]["high"] < center_high for k in range(1, lookback + 1)
        ) and all(rows[i - k]["high"] < center_high for k in range(1, lookback + 1))
        is_pivot_low = all(
            rows[i + k]["low"] > center_low for k in range(1, lookback + 1)
        ) and all(rows[i - k]["low"] > center_low for k in range(1, lookback + 1))

        if is_pivot_high:
            last_pivot_high = center_high
        if is_pivot_low:
            last_pivot_low = center_low

    # Lấy giá đóng cửa hiện tại
    close_now = rows[-1]["close"] if rows else None

    # Xác định trạng thái
    if close_now is None or last_pivot_high is None or last_pivot_low is None:
        return {
            "pivot_high": last_pivot_high,
            "pivot_low": last_pivot_low,
            "trang_thai": "TRONG_VUNG",
        }

    if close_now > last_pivot_high:
        trang_thai = "BREAKOUT_UP"
    elif close_now < last_pivot_low:
        trang_thai = "BREAKOUT_DOWN"
    else:
        trang_thai = "TRONG_VUNG"

    return {
        "pivot_high": last_pivot_high,
        "pivot_low": last_pivot_low,
        "trang_thai": trang_thai,
    }


def pt_support_resistance(df, window=20, tolerance=0.002):
    """Phân tích Support/Resistance bằng clustering mức giá được test nhiều lần."""

    # 1. Dùng Polars để lấy dữ liệu high/low/close
    df_calc = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    if n < window:
        return {
            "resistance": None,
            "support": None,
            "trang_thai": "GIUA_VUNG",
            "muc_do": "YEU",
        }

    close_now = rows[-1]["close"]

    # 2. Thu thập các mức giá đáng chú ý (đỉnh/đáy cục bộ trong window)
    candidate_levels = []
    for i in range(1, n - 1):
        h = rows[i]["high"]
        l = rows[i]["low"]
        # Đỉnh cục bộ
        if rows[i - 1]["high"] < h and rows[i + 1]["high"] < h:
            candidate_levels.append(h)
        # Đáy cục bộ
        if rows[i - 1]["low"] > l and rows[i + 1]["low"] > l:
            candidate_levels.append(l)

    if not candidate_levels:
        recent_highs = [r["high"] for r in rows[-window:]]
        recent_lows = [r["low"] for r in rows[-window:]]
        return {
            "resistance": max(recent_highs),
            "support": min(recent_lows),
            "trang_thai": "GIUA_VUNG",
            "muc_do": "YEU",
        }

    # 3. Clustering: nhóm các mức giá gần nhau (trong tolerance%) thành một cluster
    candidate_levels.sort()
    clusters = []
    current_cluster = [candidate_levels[0]]

    for level in candidate_levels[1:]:
        # Nếu mức giá mới gần với trung bình cluster hiện tại -> nhập vào
        cluster_mean = sum(current_cluster) / len(current_cluster)
        if abs(level - cluster_mean) / cluster_mean <= tolerance:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    clusters.append(current_cluster)

    # 4. Tính trung bình và số lần test của mỗi cluster
    cluster_info = [(sum(c) / len(c), len(c)) for c in clusters]

    # Tìm resistance (cluster trên giá hiện tại, nhiều lần test nhất)
    above = [(lvl, cnt) for lvl, cnt in cluster_info if lvl > close_now]
    below = [(lvl, cnt) for lvl, cnt in cluster_info if lvl < close_now]

    if above:
        resistance, res_count = min(above, key=lambda x: x[0])  # Gần nhất phía trên
    else:
        resistance = max(r["high"] for r in rows[-window:])
        res_count = 1

    if below:
        support, sup_count = max(below, key=lambda x: x[0])  # Gần nhất phía dưới
    else:
        support = min(r["low"] for r in rows[-window:])
        sup_count = 1

    # 5. Xác định trạng thái và mức độ
    dist_to_res = (resistance - close_now) / close_now if resistance else float("inf")
    dist_to_sup = (close_now - support) / close_now if support else float("inf")

    if dist_to_res < dist_to_sup and dist_to_res < tolerance * 3:
        trang_thai = "GAN_RESISTANCE"
        muc_do = "MANH" if res_count >= 3 else "YEU"
    elif dist_to_sup < dist_to_res and dist_to_sup < tolerance * 3:
        trang_thai = "GAN_SUPPORT"
        muc_do = "MANH" if sup_count >= 3 else "YEU"
    else:
        trang_thai = "GIUA_VUNG"
        muc_do = "YEU"

    return {
        "resistance": resistance,
        "support": support,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_heikin_ashi(df):
    """Phân tích Heikin Ashi bằng Polars: Hiệu suất cao."""

    df_calc = df.select(
        [
            pl.col("open"),
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    if n < 2:
        return {
            "ha_close": None,
            "ha_open": None,
            "trang_thai": "GIAM",
            "muc_do": "YEU",
        }

    # 1. Tính Heikin Ashi cho các nến gần nhất (cần ít nhất 4 nến để kiểm tra 3 liên tiếp)
    # Dùng EWM(span=2) để xấp xỉ HA_open: HA_open[i] = (HA_open[i-1] + HA_close[i-1]) / 2
    # Tính vectorized trên toàn bộ dữ liệu
    ha_closes = [(r["open"] + r["high"] + r["low"] + r["close"]) / 4 for r in rows]

    # HA_open[0]: dùng (open+close)/2 của nến đầu tiên làm seed
    ha_opens = [0.0] * n
    ha_opens[0] = (rows[0]["open"] + rows[0]["close"]) / 2
    for i in range(1, n):
        ha_opens[i] = (ha_opens[i - 1] + ha_closes[i - 1]) / 2

    # 2. Lấy giá trị của nến cuối cùng (nến Live hiện tại)
    ha_close_now = ha_closes[-1]
    ha_open_now = ha_opens[-1]

    # 3. Xác định trạng thái nến hiện tại
    trang_thai = "TANG" if ha_close_now > ha_open_now else "GIAM"

    # 4. Mức độ: MANH nếu 3 nến cuối liên tiếp cùng chiều
    # Kiểm tra None để tránh lỗi khi dữ liệu chưa đủ độ dài
    if n >= 3:
        last_3_directions = [ha_closes[i] > ha_opens[i] for i in range(n - 3, n)]
        muc_do = "MANH" if len(set(last_3_directions)) == 1 else "YEU"
    else:
        muc_do = "YEU"

    return {
        "ha_close": ha_close_now,
        "ha_open": ha_open_now,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_zigzag(df, min_change=0.03):
    """Phân tích ZigZag: tìm Swing High và Swing Low đáng kể gần nhất bằng Polars."""

    if df is None or df.height < 10:
        return {
            "zz_res": None,
            "zz_sup": None,
            "trang_thai": "TRONG_RANGE",
            "muc_do": "YEU",
        }

    df_calc = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    # Duyệt ngược để tìm swing high và swing low đã xác nhận
    # Điều kiện: thay đổi giá giữa swing high và swing low >= min_change
    last_swing_high = None
    last_swing_low = None

    # Pha 1: tìm đỉnh/đáy cục bộ từ cuối về đầu
    # Một điểm là đỉnh nếu cao hơn 2 nến hai bên; tương tự cho đáy
    for i in range(n - 2, 0, -1):
        h = rows[i]["high"]
        l = rows[i]["low"]

        if last_swing_high is None:
            if rows[i - 1]["high"] < h and rows[i + 1]["high"] < h:
                last_swing_high = h

        if last_swing_low is None:
            if rows[i - 1]["low"] > l and rows[i + 1]["low"] > l:
                last_swing_low = l

        # Dừng khi đã tìm đủ cả hai
        if last_swing_high is not None and last_swing_low is not None:
            break

    # Fallback: dùng max/min của toàn dãy nếu không tìm được pivot
    if last_swing_high is None:
        last_swing_high = max(r["high"] for r in rows)
    if last_swing_low is None:
        last_swing_low = min(r["low"] for r in rows)

    # Kiểm tra biên độ dao động tối thiểu
    if last_swing_high > 0:
        change = (last_swing_high - last_swing_low) / last_swing_high
    else:
        change = 0.0

    close_now = rows[-1]["close"]

    # Nếu biên độ quá nhỏ, không đủ ý nghĩa ZigZag
    if change < min_change:
        return {
            "zz_res": last_swing_high,
            "zz_sup": last_swing_low,
            "trang_thai": "TRONG_RANGE",
            "muc_do": "YEU",
        }

    # Xác định trạng thái
    if close_now > last_swing_high:
        trang_thai = "BREAKOUT_UP"
    elif close_now < last_swing_low:
        trang_thai = "BREAKOUT_DOWN"
    else:
        trang_thai = "TRONG_RANGE"

    # Mức độ: MANH nếu phá rõ ràng (>0.1% ngoài vùng)
    if trang_thai == "BREAKOUT_UP":
        muc_do = "MANH" if close_now > last_swing_high * 1.001 else "YEU"
    elif trang_thai == "BREAKOUT_DOWN":
        muc_do = "MANH" if close_now < last_swing_low * 0.999 else "YEU"
    else:
        muc_do = "YEU"

    return {
        "zz_res": last_swing_high,
        "zz_sup": last_swing_low,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_fvg(df):
    """Phân tích Fair Value Gap (FVG): tìm FVG chưa được lấp gần nhất trong 20 nến cuối."""

    if df is None or df.height < 3:
        return {
            "fvg_top": None,
            "fvg_bottom": None,
            "fvg_type": "NONE",
            "trang_thai": "TRONG_FVG",
            "muc_do": "YEU",
        }

    df_calc = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    scan_start = max(2, n - 20)  # Quét tối đa 20 nến cuối

    fvg_top = None
    fvg_bottom = None
    fvg_type = "NONE"

    # Duyệt ngược để tìm FVG chưa được lấp gần nhất
    for i in range(n - 1, scan_start - 1, -1):
        high_i = rows[i]["high"]
        low_i = rows[i]["low"]
        high_im2 = rows[i - 2]["high"]
        low_im2 = rows[i - 2]["low"]

        # Bullish FVG: đáy nến i > đỉnh nến i-2 (gap lên, chưa lấp)
        if low_i > high_im2:
            # Kiểm tra chưa bị lấp (giá hiện tại không đâm xuống dưới gap)
            close_now = rows[-1]["close"]
            if close_now >= high_im2:  # Chưa lấp hoàn toàn
                fvg_top = low_i
                fvg_bottom = high_im2
                fvg_type = "BULL"
                break

        # Bearish FVG: đỉnh nến i < đáy nến i-2 (gap xuống, chưa lấp)
        elif high_i < low_im2:
            close_now = rows[-1]["close"]
            if close_now <= low_im2:  # Chưa lấp hoàn toàn
                fvg_top = low_im2
                fvg_bottom = high_i
                fvg_type = "BEAR"
                break

    close_now = rows[-1]["close"]

    if fvg_type == "NONE" or fvg_top is None or fvg_bottom is None:
        return {
            "fvg_top": None,
            "fvg_bottom": None,
            "fvg_type": "NONE",
            "trang_thai": "TRONG_FVG",
            "muc_do": "YEU",
        }

    # Xác định trạng thái so với vùng FVG
    if fvg_bottom <= close_now <= fvg_top:
        trang_thai = "TRONG_FVG"
    elif close_now > fvg_top:
        trang_thai = "TREN_FVG"
    else:
        trang_thai = "DUOI_FVG"

    # Mức độ: MANH nếu FVG có biên độ lớn (>0.3% của giá)
    fvg_size = (fvg_top - fvg_bottom) / fvg_bottom if fvg_bottom > 0 else 0
    muc_do = "MANH" if fvg_size >= 0.003 else "YEU"

    return {
        "fvg_top": fvg_top,
        "fvg_bottom": fvg_bottom,
        "fvg_type": fvg_type,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_market_structure(df, swing_window=5):
    """Phân tích Cấu trúc Thị trường (BOS / CHoCH) dùng Swing High/Low bằng Polars."""

    if df is None or df.height < swing_window * 3:
        return {
            "swing_high": None,
            "swing_low": None,
            "bias": "NEUTRAL",
            "trang_thai": "TRONG_RANGE",
            "muc_do": "YEU",
        }

    df_calc = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    # Tìm swing highs và swing lows đã xác nhận (cần swing_window nến mỗi bên)
    confirmed_up_to = n - swing_window - 1
    swing_highs = []  # (index, price)
    swing_lows = []  # (index, price)

    for i in range(swing_window, confirmed_up_to + 1):
        center_high = rows[i]["high"]
        center_low = rows[i]["low"]

        is_swing_high = all(
            rows[i + k]["high"] < center_high for k in range(1, swing_window + 1)
        ) and all(rows[i - k]["high"] < center_high for k in range(1, swing_window + 1))
        is_swing_low = all(
            rows[i + k]["low"] > center_low for k in range(1, swing_window + 1)
        ) and all(rows[i - k]["low"] > center_low for k in range(1, swing_window + 1))

        if is_swing_high:
            swing_highs.append((i, center_high))
        if is_swing_low:
            swing_lows.append((i, center_low))

    # Lấy swing high và swing low gần nhất
    last_swing_high = swing_highs[-1][1] if swing_highs else None
    last_swing_low = swing_lows[-1][1] if swing_lows else None

    close_now = rows[-1]["close"]

    if last_swing_high is None or last_swing_low is None:
        return {
            "swing_high": last_swing_high,
            "swing_low": last_swing_low,
            "bias": "NEUTRAL",
            "trang_thai": "TRONG_RANGE",
            "muc_do": "YEU",
        }

    # Xác định bias từ chuỗi swing: so sánh 2 swing gần nhất
    bias = "NEUTRAL"
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        # Higher High và Higher Low -> BULL
        if (
            swing_highs[-1][1] > swing_highs[-2][1]
            and swing_lows[-1][1] > swing_lows[-2][1]
        ):
            bias = "BULL"
        # Lower High và Lower Low -> BEAR
        elif (
            swing_highs[-1][1] < swing_highs[-2][1]
            and swing_lows[-1][1] < swing_lows[-2][1]
        ):
            bias = "BEAR"
    elif len(swing_highs) >= 2:
        bias = "BULL" if swing_highs[-1][1] > swing_highs[-2][1] else "BEAR"
    elif len(swing_lows) >= 2:
        bias = "BULL" if swing_lows[-1][1] > swing_lows[-2][1] else "BEAR"

    # Xác định trạng thái BOS / CHoCH
    if close_now > last_swing_high:
        trang_thai = "BOS_UP" if bias == "BULL" else "CHOCH_BULL"
    elif close_now < last_swing_low:
        trang_thai = "BOS_DOWN" if bias == "BEAR" else "CHOCH_BEAR"
    else:
        trang_thai = "TRONG_RANGE"

    # Mức độ: MANH nếu phá vượt rõ ràng (>0.2% ngoài swing)
    if trang_thai in ("BOS_UP", "CHOCH_BULL"):
        muc_do = "MANH" if close_now > last_swing_high * 1.002 else "YEU"
    elif trang_thai in ("BOS_DOWN", "CHOCH_BEAR"):
        muc_do = "MANH" if close_now < last_swing_low * 0.998 else "YEU"
    else:
        muc_do = "YEU"

    return {
        "swing_high": last_swing_high,
        "swing_low": last_swing_low,
        "bias": bias,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_order_blocks(df, lookback=20):
    """Phân tích Order Blocks (OB): tìm Bullish OB và Bearish OB gần nhất bằng Polars."""

    if df is None or df.height < lookback:
        return {
            "ob_bull_high": None,
            "ob_bull_low": None,
            "ob_bear_high": None,
            "ob_bear_low": None,
            "trang_thai": "NGOAI_OB",
            "muc_do": "YEU",
        }

    df_calc = df.select(
        [
            pl.col("open"),
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
        ]
    )

    rows = df_calc.to_dicts()
    n = len(rows)

    # Tính average body size gần nhất (lookback nến) để xác định impulse
    recent_bodies = [
        abs(rows[i]["close"] - rows[i]["open"]) for i in range(max(0, n - lookback), n)
    ]
    avg_body = sum(recent_bodies) / len(recent_bodies) if recent_bodies else 0

    ob_bull_high = None
    ob_bull_low = None
    ob_bear_high = None
    ob_bear_low = None

    # Duyệt ngược để tìm nến impulse và OB tương ứng
    for i in range(n - 1, 0, -1):
        body_i = abs(rows[i]["close"] - rows[i]["open"])

        # Impulse tăng mạnh (nến tăng có thân > 1.5 * avg_body)
        if (
            ob_bull_high is None
            and rows[i]["close"] > rows[i]["open"]
            and avg_body > 0
            and body_i > 1.5 * avg_body
        ):
            # Tìm nến giảm (bearish) gần nhất TRƯỚC nến impulse tăng -> Bullish OB
            start = max(0, i - lookback)
            for j in range(i - 1, start - 1, -1):
                if rows[j]["close"] < rows[j]["open"]:
                    ob_bull_high = rows[j]["high"]
                    ob_bull_low = rows[j]["low"]
                    break

        # Impulse giảm mạnh (nến giảm có thân > 1.5 * avg_body)
        if (
            ob_bear_high is None
            and rows[i]["close"] < rows[i]["open"]
            and avg_body > 0
            and body_i > 1.5 * avg_body
        ):
            # Tìm nến tăng (bullish) gần nhất TRƯỚC nến impulse giảm -> Bearish OB
            start = max(0, i - lookback)
            for j in range(i - 1, start - 1, -1):
                if rows[j]["close"] > rows[j]["open"]:
                    ob_bear_high = rows[j]["high"]
                    ob_bear_low = rows[j]["low"]
                    break

        # Dừng khi đã tìm đủ cả hai loại OB
        if ob_bull_high is not None and ob_bear_high is not None:
            break

    close_now = rows[-1]["close"]

    # Xác định trạng thái: giá có đang nằm trong vùng OB nào không
    in_bull_ob = (
        ob_bull_high is not None
        and ob_bull_low is not None
        and ob_bull_low <= close_now <= ob_bull_high
    )
    in_bear_ob = (
        ob_bear_high is not None
        and ob_bear_low is not None
        and ob_bear_low <= close_now <= ob_bear_high
    )

    if in_bull_ob:
        trang_thai = "TRONG_BULL_OB"
        muc_do = "MANH"
    elif in_bear_ob:
        trang_thai = "TRONG_BEAR_OB"
        muc_do = "MANH"
    else:
        trang_thai = "NGOAI_OB"
        muc_do = "YEU"

    return {
        "ob_bull_high": ob_bull_high,
        "ob_bull_low": ob_bull_low,
        "ob_bear_high": ob_bear_high,
        "ob_bear_low": ob_bear_low,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }
