"""BIẾN ĐỘNG (Volatility)
👉 Giá chạy mạnh hay yếu?
- ATR
- Bollinger Bands
- Keltner Channel
- Donchian Channel
📌 Dùng cho SL / TP / leverage"""

import polars as pl


def pt_atr(df, window=14, mean_window=100):
    """Phân tích ATR bằng Polars Native Expression."""

    # 1. Tính True Range và ATR ngay trong DF
    df_result = df.with_columns(
        [
            pl.max_horizontal(
                pl.col("high") - pl.col("low"),
                (pl.col("high") - pl.col("close").shift(1)).abs(),
                (pl.col("low") - pl.col("close").shift(1)).abs(),
            )
            .ewm_mean(span=window)
            .alias("atr_series")
        ]
    ).with_columns(
        [
            pl.col("atr_series")
            .rolling_mean(window_size=mean_window)
            .alias("atr_mean_series")
        ]
    )

    # 2. Trích xuất giá trị dòng cuối cùng
    # Polars dùng .tail(1) và chuyển thành dict
    last_row = df_result.tail(1).to_dicts()[0]

    atr_now = last_row["atr_series"]
    atr_mean = last_row["atr_mean_series"]

    # Kiểm tra null (đề phòng dữ liệu quá ngắn)
    if atr_now is None or atr_mean is None:
        return None

    trang_thai = "BIẾN_ĐỘNG_CAO" if atr_now > atr_mean else "BIẾN_ĐỘNG_THẤP"

    return {
        "atr_val": atr_now,
        "atr_mean": atr_mean,
        "trang_thai": trang_thai,
        "muc_do": "CAO" if atr_now > atr_mean else "THAP",
    }


def pt_bollinger_squeeze(df, window=20, window_dev=2):
    """Phân tích Bollinger Bands Squeeze bằng Polars Native Expression."""

    # 1. Tính toán các đường BB ngay trong DataFrame
    df_bb = (
        df.with_columns(
            [
                pl.col("close").rolling_mean(window_size=window).alias("mid_band"),
                pl.col("close").rolling_std(window_size=window).alias("std_dev"),
            ]
        )
        .with_columns(
            [
                (pl.col("mid_band") + (window_dev * pl.col("std_dev"))).alias(
                    "upper_band"
                ),
                (pl.col("mid_band") - (window_dev * pl.col("std_dev"))).alias(
                    "lower_band"
                ),
            ]
        )
        .with_columns(
            [
                # Tính Bandwidth: (High - Low) / Mid
                (
                    (pl.col("upper_band") - pl.col("lower_band"))
                    / (pl.col("mid_band") + 1e-9)
                ).alias("w_band")
            ]
        )
        .with_columns(
            [
                # Tính trung bình Bandwidth để so sánh độ nén
                pl.col("w_band")
                .rolling_mean(window_size=50)
                .alias("w_band_mean")
            ]
        )
    )

    # 2. Trích xuất dòng cuối cùng
    last = df_bb.tail(1).to_dicts()[0]

    w_band_val = last["w_band"]
    w_band_mean = last["w_band_mean"]

    # 3. Logic phân loại
    trang_thai = "BOP" if w_band_val < w_band_mean * 0.8 else "MO_RONG"
    muc_do = "CHAT" if w_band_val < w_band_mean * 0.6 else "THUONG"

    return {
        "upper_band": last["upper_band"],
        "lower_band": last["lower_band"],
        "mid_band": last["mid_band"],
        "bandwidth": w_band_val,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_keltner_channel(df, window=20, atr_mult=1.5):
    """Phân tích Keltner Channel bằng Polars Native Expression."""

    df_kc = df.with_columns(
        [
            pl.col("close").ewm_mean(span=window).alias("kc_ema"),
            pl.max_horizontal(
                pl.col("high") - pl.col("low"),
                (pl.col("high") - pl.col("close").shift(1)).abs(),
                (pl.col("low") - pl.col("close").shift(1)).abs(),
            )
            .ewm_mean(span=window)
            .alias("kc_atr"),
        ]
    ).with_columns(
        [
            (pl.col("kc_ema") + atr_mult * pl.col("kc_atr")).alias("kc_upper"),
            (pl.col("kc_ema") - atr_mult * pl.col("kc_atr")).alias("kc_lower"),
        ]
    )

    last = df_kc.tail(1).to_dicts()[0]

    kc_upper = last["kc_upper"]
    kc_lower = last["kc_lower"]
    kc_mid = last["kc_ema"]
    close_val = last["close"]

    if kc_upper is None or kc_lower is None or kc_mid is None:
        return None

    if close_val > kc_upper:
        trang_thai = "TREN"
    elif close_val < kc_lower:
        trang_thai = "DUOI"
    else:
        trang_thai = "TRONG"

    kc_range = kc_upper - kc_lower
    kc_mean_range = df_kc.select(
        (pl.col("kc_upper") - pl.col("kc_lower")).rolling_mean(window_size=50).last()
    ).item()
    muc_do = (
        "CAO" if (kc_mean_range is not None and kc_range > kc_mean_range) else "THAP"
    )

    return {
        "kc_upper": kc_upper,
        "kc_lower": kc_lower,
        "kc_mid": kc_mid,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_donchian_channel(df, window=20):
    """Phân tích Donchian Channel bằng Polars Native Expression."""

    df_dc = (
        df.with_columns(
            [
                pl.col("high").rolling_max(window_size=window).alias("dc_upper"),
                pl.col("low").rolling_min(window_size=window).alias("dc_lower"),
            ]
        )
        .with_columns([((pl.col("dc_upper") + pl.col("dc_lower")) / 2).alias("dc_mid")])
        .with_columns(
            [
                (
                    (pl.col("dc_upper") - pl.col("dc_lower"))
                    / (pl.col("dc_mid") + 1e-9)
                ).alias("dc_width")
            ]
        )
    )

    last = df_dc.tail(1).to_dicts()[0]

    dc_upper = last["dc_upper"]
    dc_lower = last["dc_lower"]
    dc_mid = last["dc_mid"]
    dc_width = last["dc_width"]
    close_val = last["close"]

    if dc_upper is None or dc_lower is None or dc_mid is None:
        return None

    # Xác định trạng thái breakout
    prev_upper = df_dc["dc_upper"][-2] if len(df_dc) > 1 else None
    prev_lower = df_dc["dc_lower"][-2] if len(df_dc) > 1 else None

    if prev_upper is not None and close_val >= dc_upper and close_val > prev_upper:
        trang_thai = "BREAKOUT_UP"
    elif prev_lower is not None and close_val <= dc_lower and close_val < prev_lower:
        trang_thai = "BREAKOUT_DOWN"
    else:
        trang_thai = "TRONG_KENH"

    # Độ rộng kênh so với trung bình 50 nến
    dc_width_mean = df_dc.select(
        pl.col("dc_width").rolling_mean(window_size=50).last()
    ).item()
    muc_do = (
        "RONG" if (dc_width_mean is not None and dc_width > dc_width_mean) else "HEP"
    )

    return {
        "dc_upper": dc_upper,
        "dc_lower": dc_lower,
        "dc_mid": dc_mid,
        "dc_width": dc_width,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_historical_volatility(df, window=20):
    """Phân tích Historical Volatility (HV) bằng Polars Native Expression."""
    import math

    df_hv = (
        df.with_columns(
            [
                (pl.col("close") / pl.col("close").shift(1))
                .log(base=math.e)
                .alias("log_ret")
            ]
        )
        .with_columns(
            [
                (
                    pl.col("log_ret").rolling_std(window_size=window)
                    * math.sqrt(252 * 390)
                ).alias("hv_series")
            ]
        )
        .with_columns(
            [pl.col("hv_series").rolling_mean(window_size=50).alias("hv_mean_50")]
        )
    )

    last = df_hv.tail(1).to_dicts()[0]

    hv_val = last["hv_series"]
    hv_mean = last["hv_mean_50"]

    if hv_val is None:
        return None

    # So sánh HV hiện tại với ngưỡng trung bình để phân loại trạng thái
    if hv_mean is not None:
        if hv_val > hv_mean * 1.2:
            trang_thai = "CAO"
        elif hv_val < hv_mean * 0.8:
            trang_thai = "THAP"
        else:
            trang_thai = "BINH_THUONG"
    else:
        trang_thai = "BINH_THUONG"

    muc_do = "CAO" if (hv_mean is not None and hv_val > hv_mean) else "THAP"

    return {"hv_val": hv_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_chaikin_volatility(df, window=10):
    """Phân tích Chaikin Volatility bằng Polars Native Expression."""

    if df is None or df.height < window * 2:
        return {"cv_val": None, "trang_thai": "GIAM", "muc_do": "YEU"}

    df_cv = (
        df.with_columns([(pl.col("high") - pl.col("low")).alias("hl")])
        .with_columns(
            [pl.col("hl").ewm_mean(span=window, adjust=False).alias("hl_ema")]
        )
        .with_columns(
            [
                (
                    (pl.col("hl_ema") - pl.col("hl_ema").shift(window))
                    / (pl.col("hl_ema").shift(window) + 1e-9)
                    * 100
                ).alias("cv_series")
            ]
        )
    )

    last = df_cv.tail(1).to_dicts()[0]

    cv_val = last["cv_series"]

    if cv_val is None:
        return {"cv_val": None, "trang_thai": "GIAM", "muc_do": "YEU"}

    trang_thai = "TANG" if cv_val > 0 else "GIAM"
    muc_do = "MANH" if abs(cv_val) > 5 else "YEU"

    return {"cv_val": cv_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_atr_bands(df, window=20, multiplier=2.5):
    """Phân tích ATR Bands bằng Polars Native Expression."""

    if df is None or df.height < window * 2:
        return {
            "atrb_upper": None,
            "atrb_lower": None,
            "atrb_mid": None,
            "trang_thai": "TRONG",
            "muc_do": "THAP",
        }

    df_atrb = (
        df.with_columns(
            [
                pl.col("close").rolling_mean(window_size=window).alias("atrb_sma"),
                pl.max_horizontal(
                    pl.col("high") - pl.col("low"),
                    (pl.col("high") - pl.col("close").shift(1)).abs(),
                    (pl.col("low") - pl.col("close").shift(1)).abs(),
                )
                .ewm_mean(span=window, adjust=False)
                .alias("atrb_atr"),
            ]
        )
        .with_columns(
            [
                (pl.col("atrb_sma") + multiplier * pl.col("atrb_atr")).alias(
                    "atrb_upper"
                ),
                (pl.col("atrb_sma") - multiplier * pl.col("atrb_atr")).alias(
                    "atrb_lower"
                ),
            ]
        )
        .with_columns(
            [(pl.col("atrb_upper") - pl.col("atrb_lower")).alias("band_width")]
        )
        .with_columns(
            [pl.col("band_width").rolling_mean(window_size=50).alias("band_width_mean")]
        )
    )

    last = df_atrb.tail(1).to_dicts()[0]

    atrb_upper = last["atrb_upper"]
    atrb_lower = last["atrb_lower"]
    atrb_mid = last["atrb_sma"]
    close_val = last["close"]
    band_width = last["band_width"]
    band_width_mean = last["band_width_mean"]

    if atrb_upper is None or atrb_lower is None or atrb_mid is None:
        return {
            "atrb_upper": None,
            "atrb_lower": None,
            "atrb_mid": None,
            "trang_thai": "TRONG",
            "muc_do": "THAP",
        }

    if close_val > atrb_upper:
        trang_thai = "TREN"
    elif close_val < atrb_lower:
        trang_thai = "DUOI"
    else:
        trang_thai = "TRONG"

    muc_do = (
        "CAO"
        if (band_width_mean is not None and band_width > band_width_mean)
        else "THAP"
    )

    return {
        "atrb_upper": atrb_upper,
        "atrb_lower": atrb_lower,
        "atrb_mid": atrb_mid,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }
