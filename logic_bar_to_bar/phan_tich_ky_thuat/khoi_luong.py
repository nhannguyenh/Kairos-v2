"""KHỐI LƯỢNG (Volume / Participation)
👉 Có tiền thật vào không?
- Volume
- Volume MA
- OBV
- VWAP
- Volume Profile
📌 Dùng để xác nhận tín hiệu"""

import polars as pl


def pt_volume(df, window=20):
    """Phân tích khối lượng giao dịch so với trung bình rolling bằng Polars."""
    # 1. Tính toán Volume trung bình (Rolling Mean)
    df_vol = df.select(
        [
            pl.col("volume"),
            pl.col("volume").rolling_mean(window_size=window).alias("vol_mean"),
        ]
    )

    # 2. Trích xuất dòng cuối cùng
    last = df_vol.tail(1).to_dicts()[0]

    vol_now = last["volume"]
    vol_mean = last["vol_mean"]

    # Kiểm tra None nếu dữ liệu chưa đủ độ dài cửa sổ (window)
    if vol_mean is None or vol_mean == 0:
        return {"vol_now": vol_now, "vol_mean": 0, "trang_thai": "KHONG_XAC_DINH"}

    # 3. Logic phân loại trạng thái
    if vol_now > vol_mean * 2:
        trang_thai = "DOT_BIEN"
    elif vol_now > vol_mean:
        trang_thai = "TANG"
    else:
        trang_thai = "THAP"

    return {"vol_now": vol_now, "vol_mean": vol_mean, "trang_thai": trang_thai}


def pt_obv(df):
    """On-Balance Volume: xác định tích lũy/phân phối qua slope OBV vs slope giá 5 nến."""
    # 1. Tính OBV theo từng nến
    df_obv = df.select(
        [
            pl.col("close"),
            pl.col("volume"),
            pl.when(pl.col("close") > pl.col("close").shift(1))
            .then(pl.col("volume"))
            .when(pl.col("close") < pl.col("close").shift(1))
            .then(-pl.col("volume"))
            .otherwise(0)
            .alias("obv_delta"),
        ]
    ).with_columns(pl.col("obv_delta").cum_sum().alias("obv"))

    # 2. Trích xuất dòng cuối cùng
    last = df_obv.tail(1).to_dicts()[0]
    obv_now = last["obv"]

    # 3. So sánh slope OBV và slope giá trong 5 nến cuối
    tail5 = df_obv.tail(5).to_dicts()
    obv_slope = tail5[-1]["obv"] - tail5[0]["obv"]
    price_slope = tail5[-1]["close"] - tail5[0]["close"]

    obv_trend = "TANG" if obv_slope > 0 else "GIAM"

    # Tích lũy: OBV tăng (tiền vào); Phân phối: OBV giảm (tiền ra)
    if obv_slope > 0 and price_slope > 0:
        trang_thai = "TICH_LUY"
        muc_do = "MANH"
    elif obv_slope > 0 and price_slope <= 0:
        trang_thai = "TICH_LUY"  # Phân kỳ tăng
        muc_do = "YEU"
    elif obv_slope < 0 and price_slope < 0:
        trang_thai = "PHAN_PHOI"
        muc_do = "MANH"
    else:
        trang_thai = "PHAN_PHOI"  # Phân kỳ giảm
        muc_do = "YEU"

    return {
        "obv_val": obv_now,
        "obv_trend": obv_trend,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_vwap(df, session_window=390):
    """Rolling VWAP trong session_window nến gần nhất (mặc định 390 = 1 ngày giao dịch 1m)."""
    # 1. Lấy session_window nến cuối
    df_w = df.tail(session_window)

    # 2. Tính typical price và VWAP tổng phiên
    df_pv = df_w.select(
        [
            pl.col("close"),
            ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("tp"),
            pl.col("volume"),
        ]
    ).with_columns((pl.col("tp") * pl.col("volume")).alias("pv"))

    totals = df_pv.select(
        [
            pl.col("pv").sum().alias("pv_sum"),
            pl.col("volume").sum().alias("vol_sum"),
            pl.col("close").last().alias("close_now"),
        ]
    ).to_dicts()[0]

    pv_sum = totals["pv_sum"]
    vol_sum = totals["vol_sum"]
    close_now = totals["close_now"]

    if vol_sum is None or vol_sum == 0:
        return {
            "vwap_val": None,
            "price_now": close_now,
            "trang_thai": "KHONG_XAC_DINH",
            "muc_do": "KHONG_XAC_DINH",
        }

    # 3. Tính VWAP và khoảng cách
    vwap_val = pv_sum / vol_sum
    dist_pct = abs(close_now - vwap_val) / vwap_val if vwap_val != 0 else 0

    trang_thai = "TREN" if close_now >= vwap_val else "DUOI"
    muc_do = "XA" if dist_pct > 0.01 else "GAN"

    return {
        "vwap_val": round(vwap_val, 6),
        "price_now": close_now,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_cmf(df, window=20):
    """Chaikin Money Flow: CMF = sum(MFM * volume, window) / sum(volume, window)."""
    # 1. Tính Money Flow Multiplier và Money Flow Volume
    df_mfv = df.select(
        [
            pl.col("high"),
            pl.col("low"),
            pl.col("close"),
            pl.col("volume"),
            pl.when((pl.col("high") - pl.col("low")) == 0)
            .then(0.0)
            .otherwise(
                ((pl.col("close") - pl.col("low")) - (pl.col("high") - pl.col("close")))
                / (pl.col("high") - pl.col("low"))
            )
            .alias("mfm"),
        ]
    ).with_columns((pl.col("mfm") * pl.col("volume")).alias("mfv"))

    # 2. Rolling sum rồi tính CMF
    df_cmf = df_mfv.select(
        [
            pl.col("mfv").rolling_sum(window_size=window).alias("pv_sum"),
            pl.col("volume").rolling_sum(window_size=window).alias("vol_sum"),
        ]
    ).with_columns(
        pl.when(pl.col("vol_sum") == 0)
        .then(None)
        .otherwise(pl.col("pv_sum") / pl.col("vol_sum"))
        .alias("cmf")
    )

    # 3. Trích xuất dòng cuối cùng
    last = df_cmf.tail(1).to_dicts()[0]
    cmf_val = last["cmf"]

    if cmf_val is None:
        return {"cmf_val": None, "trang_thai": "TRUNG_TINH", "muc_do": "YEU"}

    # 4. Phân loại
    if cmf_val > 0.1:
        trang_thai = "MUA"
        muc_do = "MANH"
    elif cmf_val > 0:
        trang_thai = "MUA"
        muc_do = "YEU"
    elif cmf_val < -0.1:
        trang_thai = "BAN"
        muc_do = "MANH"
    elif cmf_val < 0:
        trang_thai = "BAN"
        muc_do = "YEU"
    else:
        trang_thai = "TRUNG_TINH"
        muc_do = "YEU"

    return {"cmf_val": round(cmf_val, 6), "trang_thai": trang_thai, "muc_do": muc_do}


def pt_ad_line(df):
    """Accumulation/Distribution Line: AD = cumsum(CLV * volume), xác định tích lũy/phân phối."""
    # 1. Tính CLV và AD tích lũy
    df_ad = (
        df.select(
            [
                pl.col("close"),
                pl.col("high"),
                pl.col("low"),
                pl.col("volume"),
                pl.when((pl.col("high") - pl.col("low")) == 0)
                .then(0.0)
                .otherwise(
                    (
                        (pl.col("close") - pl.col("low"))
                        - (pl.col("high") - pl.col("close"))
                    )
                    / (pl.col("high") - pl.col("low"))
                )
                .alias("clv"),
            ]
        )
        .with_columns((pl.col("clv") * pl.col("volume")).alias("adv"))
        .with_columns(pl.col("adv").cum_sum().alias("ad"))
    )

    # 2. Trích xuất dòng cuối cùng
    last = df_ad.tail(1).to_dicts()[0]
    ad_val = last["ad"]

    # 3. So sánh slope AD trong 5 nến cuối
    tail5 = df_ad.tail(5).to_dicts()
    ad_slope = tail5[-1]["ad"] - tail5[0]["ad"]

    trang_thai = "TICH_LUY" if ad_slope > 0 else "PHAN_PHOI"
    muc_do = "MANH" if abs(ad_slope) > abs(tail5[0]["ad"]) * 0.01 else "YEU"

    return {"ad_val": round(ad_val, 4), "trang_thai": trang_thai, "muc_do": muc_do}


def pt_volume_ma_dual(df, fast=5, slow=20):
    """Dual Volume MA: so sánh volume MA nhanh vs chậm để phát hiện surge/dry."""
    # 1. Null guard
    if df is None or df.height < slow:
        return {
            "vol_ma_fast": None,
            "vol_ma_slow": None,
            "trang_thai": "KHONG_XAC_DINH",
            "muc_do": "YEU",
        }

    # 2. Tính hai Volume MA
    df_ma = df.select(
        [
            pl.col("volume").rolling_mean(window_size=fast).alias("vol_ma_fast"),
            pl.col("volume").rolling_mean(window_size=slow).alias("vol_ma_slow"),
        ]
    )

    # 3. Trích xuất dòng cuối cùng
    last = df_ma.tail(1).to_dicts()[0]
    vol_ma_fast = last["vol_ma_fast"]
    vol_ma_slow = last["vol_ma_slow"]

    if vol_ma_fast is None or vol_ma_slow is None or vol_ma_slow == 0:
        return {
            "vol_ma_fast": vol_ma_fast,
            "vol_ma_slow": vol_ma_slow,
            "trang_thai": "KHONG_XAC_DINH",
            "muc_do": "YEU",
        }

    # 4. Phân loại trạng thái và mức độ
    if vol_ma_fast > vol_ma_slow * 1.5:
        trang_thai = "SURGE"
        muc_do = "MANH"
    elif vol_ma_fast < vol_ma_slow * 0.5:
        trang_thai = "DRY"
        muc_do = "YEU"
    elif vol_ma_fast > vol_ma_slow:
        trang_thai = "TANG"
        muc_do = "MANH"
    else:
        trang_thai = "GIAM"
        muc_do = "YEU"

    return {
        "vol_ma_fast": round(vol_ma_fast, 4),
        "vol_ma_slow": round(vol_ma_slow, 4),
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_volume_profile(df, bins=20):
    """Volume Profile đơn giản hóa: tìm POC, VAH, VAL dựa trên phân phối volume theo giá."""
    # 1. Null guard
    if df is None or df.height < bins:
        return {
            "poc": None,
            "vah": None,
            "val": None,
            "trang_thai": "KHONG_XAC_DINH",
            "muc_do": "NGOAI_VA",
        }

    # 2. Chuyển sang pandas để xử lý bins
    pdf = df.select(["close", "volume"]).to_pandas()

    price_min = pdf["close"].min()
    price_max = pdf["close"].max()

    if price_max == price_min:
        return {
            "poc": price_min,
            "vah": price_max,
            "val": price_min,
            "trang_thai": "TAI_POC",
            "muc_do": "TRONG_VA",
        }

    # 3. Tạo bins và tính volume mỗi bucket
    import numpy as np

    edges = np.linspace(price_min, price_max, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    vol_bins = np.zeros(bins)

    for _, row in pdf.iterrows():
        idx = min(
            int((row["close"] - price_min) / (price_max - price_min) * bins), bins - 1
        )
        vol_bins[idx] += row["volume"]

    # 4. POC = center của bucket có volume lớn nhất
    poc_idx = int(np.argmax(vol_bins))
    poc = float(centers[poc_idx])

    # 5. Value Area: 70% tổng volume, mở rộng từ POC ra hai phía
    total_vol = vol_bins.sum()
    target_vol = total_vol * 0.70
    va_low_idx = poc_idx
    va_high_idx = poc_idx
    va_vol = vol_bins[poc_idx]

    while va_vol < target_vol:
        expand_low = va_low_idx > 0
        expand_high = va_high_idx < bins - 1
        if not expand_low and not expand_high:
            break
        add_low = vol_bins[va_low_idx - 1] if expand_low else -1
        add_high = vol_bins[va_high_idx + 1] if expand_high else -1
        if add_high >= add_low:
            va_high_idx += 1
            va_vol += vol_bins[va_high_idx]
        else:
            va_low_idx -= 1
            va_vol += vol_bins[va_low_idx]

    vah = float(edges[va_high_idx + 1])
    val = float(edges[va_low_idx])

    # 6. Trích xuất giá đóng cửa gần nhất
    close_now = pdf["close"].iloc[-1]

    # 7. Phân loại trạng thái
    if abs(close_now - poc) / poc < 0.001:
        trang_thai = "TAI_POC"
    elif close_now > poc:
        trang_thai = "TREN_POC"
    else:
        trang_thai = "DUOI_POC"

    muc_do = "TRONG_VA" if val <= close_now <= vah else "NGOAI_VA"

    return {
        "poc": round(poc, 6),
        "vah": round(vah, 6),
        "val": round(val, 6),
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_mfi_volume(df, window=14):
    """Money Flow Index (MFI): volume-weighted RSI dựa trên typical price và raw money flow."""
    # 1. Null guard
    if df is None or df.height < window + 1:
        return {"mfi_val": None, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    # 2. Tính typical price và raw money flow
    df_mf = (
        df.select(
            [
                pl.col("high"),
                pl.col("low"),
                pl.col("close"),
                pl.col("volume"),
                ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("tp"),
            ]
        )
        .with_columns(
            (pl.col("tp") * pl.col("volume")).alias("raw_mf"),
            pl.col("tp").shift(1).alias("prev_tp"),
        )
        .with_columns(
            pl.when(pl.col("tp") > pl.col("prev_tp"))
            .then(pl.col("raw_mf"))
            .otherwise(0.0)
            .alias("pos_mf"),
            pl.when(pl.col("tp") < pl.col("prev_tp"))
            .then(pl.col("raw_mf"))
            .otherwise(0.0)
            .alias("neg_mf"),
        )
    )

    # 3. Rolling sum trong window nến
    df_sums = df_mf.select(
        [
            pl.col("pos_mf").rolling_sum(window_size=window).alias("pos_sum"),
            pl.col("neg_mf").rolling_sum(window_size=window).alias("neg_sum"),
        ]
    )

    # 4. Trích xuất dòng cuối cùng
    last = df_sums.tail(1).to_dicts()[0]
    pos_sum = last["pos_sum"]
    neg_sum = last["neg_sum"]

    if pos_sum is None or neg_sum is None:
        return {"mfi_val": None, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    if neg_sum == 0:
        mfi_val = 100.0
    else:
        mfi_val = 100.0 - 100.0 / (1.0 + pos_sum / neg_sum)

    # 5. Phân loại trạng thái và mức độ
    if mfi_val >= 80:
        trang_thai = "QUA_MUA"
        muc_do = "MANH"
    elif mfi_val <= 20:
        trang_thai = "QUA_BAN"
        muc_do = "MANH"
    else:
        trang_thai = "BINH_THUONG"
        muc_do = "YEU"

    return {"mfi_val": round(mfi_val, 4), "trang_thai": trang_thai, "muc_do": muc_do}


def pt_ease_of_movement(df, window=14):
    """Ease of Movement (EOM): đo mức độ dễ dàng giá di chuyển dựa trên volume."""
    # 1. Null guard
    if df is None or df.height < window + 1:
        return {"eom_val": None, "trang_thai": "TANG", "muc_do": "YEU"}

    # 2. Chuyển sang pandas để xử lý rolling dễ hơn
    pdf = df.select(["high", "low", "volume"]).to_pandas()

    mid = (pdf["high"] + pdf["low"]) / 2.0
    prev_mid = mid.shift(1)
    hl_range = (pdf["high"] - pdf["low"]).replace(0, float("nan"))
    box_ratio = pdf["volume"] / hl_range

    eom = (mid - prev_mid) / box_ratio
    eom_sma = eom.rolling(window).mean()

    eom_val = float(eom_sma.iloc[-1]) if not eom_sma.isna().iloc[-1] else None

    if eom_val is None:
        return {"eom_val": None, "trang_thai": "TANG", "muc_do": "YEU"}

    # 3. Phân loại trạng thái
    trang_thai = "TANG" if eom_val > 0 else "GIAM"

    # 4. Mức độ: so sánh |eom_sma| với rolling mean của |eom|
    eom_abs_mean = eom.abs().rolling(window).mean().iloc[-1]
    if eom_abs_mean and abs(eom_val) > eom_abs_mean * 0.5:
        muc_do = "MANH"
    else:
        muc_do = "YEU"

    return {"eom_val": round(eom_val, 8), "trang_thai": trang_thai, "muc_do": muc_do}
