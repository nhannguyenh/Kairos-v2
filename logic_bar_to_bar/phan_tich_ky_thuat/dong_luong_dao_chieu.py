"""ĐẢO CHIỀU / ĐỘNG LƯỢNG (Momentum / Reversal)
👉 Lực đang yếu đi hay mạnh lên?
- RSI
- Stochastic
- CCI
- Williams %R
- ROC
📌 Dùng để timing entry / exit"""

import polars as pl


def pt_rsi(df, window=14):
    """Phân tích RSI bằng Polars: đánh giá trạng thái quá mua/quá bán."""
    # 1. Tính toán RSI trực tiếp (Công thức tối ưu hóa cho Polars)
    df_rsi = df.with_columns([pl.col("close").diff().alias("diff")]).with_columns(
        [
            (
                100
                - (
                    100
                    / (
                        1
                        + (
                            pl.when(pl.col("diff") >= 0)
                            .then(pl.col("diff"))
                            .otherwise(0)
                            .ewm_mean(span=window)
                            / pl.when(pl.col("diff") < 0)
                            .then(pl.col("diff").abs())
                            .otherwise(1e-9)
                            .ewm_mean(span=window)
                        )
                    )
                )
            ).alias("rsi_series")
        ]
    )

    # 2. Trích xuất giá trị cuối cùng
    last_row = df_rsi.tail(1).to_dicts()[0]
    rsi_val = last_row["rsi_series"]

    # Kiểm tra giá trị null nếu dữ liệu quá ngắn
    if rsi_val is None:
        return {"rsi_val": 50.0, "trang_thai": "TRUNG_TÍNH", "muc_do": "THƯỜNG"}

    # 3. Phân loại trạng thái
    if rsi_val > 60:
        trang_thai = "MẠNH"
    elif rsi_val < 40:
        trang_thai = "YẾU"
    else:
        trang_thai = "TRUNG_TÍNH"

    # Phân loại mức độ quá mua/quá bán
    if rsi_val > 70:
        muc_do = "QUÁ_MUA"
    elif rsi_val < 30:
        muc_do = "QUÁ_BÁN"
    else:
        muc_do = "THƯỜNG"

    return {"rsi_val": rsi_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_stochastic(df, k_window=14, d_window=3):
    """Phân tích Stochastic Oscillator bằng Polars: đánh giá vùng quá mua/quá bán."""
    # 1. Tính toán %K và %D
    df_stoch = (
        df.with_columns(
            [
                pl.col("low").rolling_min(window_size=k_window).alias("low_min"),
                pl.col("high").rolling_max(window_size=k_window).alias("high_max"),
            ]
        )
        .with_columns(
            [
                pl.when((pl.col("high_max") - pl.col("low_min")) == 0)
                .then(1e-9)
                .otherwise(pl.col("high_max") - pl.col("low_min"))
                .alias("denom")
            ]
        )
        .with_columns(
            [
                (100 * (pl.col("close") - pl.col("low_min")) / pl.col("denom")).alias(
                    "stoch_k_series"
                )
            ]
        )
        .with_columns(
            [
                pl.col("stoch_k_series")
                .rolling_mean(window_size=d_window)
                .alias("stoch_d_series")
            ]
        )
    )

    # 2. Trích xuất giá trị cuối cùng
    last_row = df_stoch.tail(1).to_dicts()[0]
    stoch_k = last_row["stoch_k_series"]
    stoch_d = last_row["stoch_d_series"]

    if stoch_k is None:
        return {
            "stoch_k": 50.0,
            "stoch_d": 50.0,
            "trang_thai": "BINH_THUONG",
            "muc_do": "YEU",
        }

    # 3. Phân loại trạng thái
    if stoch_k > 80:
        trang_thai = "QUA_MUA"
        muc_do = "MANH" if stoch_k > 90 else "YEU"
    elif stoch_k < 20:
        trang_thai = "QUA_BAN"
        muc_do = "MANH" if stoch_k < 10 else "YEU"
    else:
        trang_thai = "BINH_THUONG"
        muc_do = "YEU"

    return {
        "stoch_k": stoch_k,
        "stoch_d": stoch_d if stoch_d is not None else stoch_k,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_cci(df, window=20):
    """Phân tích Commodity Channel Index (CCI) bằng Polars."""
    # 1. Tính toán CCI
    df_cci = (
        df.with_columns(
            [((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("tp")]
        )
        .with_columns([pl.col("tp").rolling_mean(window_size=window).alias("sma_tp")])
        .with_columns(
            [
                (pl.col("tp") - pl.col("sma_tp"))
                .abs()
                .rolling_mean(window_size=window)
                .alias("mean_dev")
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("mean_dev") == 0)
                .then(None)
                .otherwise(
                    (pl.col("tp") - pl.col("sma_tp")) / (0.015 * pl.col("mean_dev"))
                )
                .alias("cci_series")
            ]
        )
    )

    # 2. Trích xuất giá trị cuối cùng
    last_row = df_cci.tail(1).to_dicts()[0]
    cci_val = last_row["cci_series"]

    if cci_val is None:
        return {"cci_val": 0.0, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    # 3. Phân loại trạng thái
    if cci_val > 100:
        trang_thai = "QUA_MUA"
        muc_do = "MANH" if cci_val > 200 else "YEU"
    elif cci_val < -100:
        trang_thai = "QUA_BAN"
        muc_do = "MANH" if cci_val < -200 else "YEU"
    else:
        trang_thai = "BINH_THUONG"
        muc_do = "YEU"

    return {"cci_val": cci_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_williams_r(df, window=14):
    """Phân tích Williams %R bằng Polars: đo lường vị trí giá trong vùng cao-thấp."""
    # 1. Tính toán Williams %R
    df_wr = df.with_columns(
        [
            pl.col("high").rolling_max(window_size=window).alias("high_max"),
            pl.col("low").rolling_min(window_size=window).alias("low_min"),
        ]
    ).with_columns(
        [
            pl.when((pl.col("high_max") - pl.col("low_min")) == 0)
            .then(None)
            .otherwise(
                (pl.col("high_max") - pl.col("close"))
                / (pl.col("high_max") - pl.col("low_min"))
                * -100
            )
            .alias("wr_series")
        ]
    )

    # 2. Trích xuất giá trị cuối cùng
    last_row = df_wr.tail(1).to_dicts()[0]
    wr_val = last_row["wr_series"]

    if wr_val is None:
        return {"wr_val": -50.0, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    # 3. Phân loại trạng thái
    if wr_val > -20:
        trang_thai = "QUA_MUA"
        muc_do = "MANH" if wr_val > -10 else "YEU"
    elif wr_val < -80:
        trang_thai = "QUA_BAN"
        muc_do = "MANH" if wr_val < -90 else "YEU"
    else:
        trang_thai = "BINH_THUONG"
        muc_do = "YEU"

    return {"wr_val": wr_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_roc(df, window=10):
    """Phân tích Rate of Change (ROC) bằng Polars: đo tốc độ thay đổi giá."""
    # 1. Tính toán ROC
    df_roc = df.with_columns(
        [pl.col("close").shift(window).alias("close_prev")]
    ).with_columns(
        [
            pl.when(pl.col("close_prev") == 0)
            .then(None)
            .otherwise(
                (pl.col("close") - pl.col("close_prev")) / pl.col("close_prev") * 100
            )
            .alias("roc_series")
        ]
    )

    # 2. Trích xuất giá trị cuối cùng
    last_row = df_roc.tail(1).to_dicts()[0]
    roc_val = last_row["roc_series"]

    if roc_val is None:
        return {"roc_val": 0.0, "trang_thai": "TANG", "muc_do": "YEU"}

    # 3. Phân loại trạng thái
    trang_thai = "TANG" if roc_val >= 0 else "GIAM"
    muc_do = "MANH" if abs(roc_val) > 2.0 else "YEU"

    return {"roc_val": roc_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_mfi(df, window=14):
    """Phân tích Money Flow Index (MFI) bằng Polars: RSI có trọng số khối lượng."""
    # 1. Tính toán MFI
    df_mfi = (
        df.with_columns(
            [((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("tp")]
        )
        .with_columns(
            [
                (pl.col("tp") * pl.col("volume")).alias("mf"),
                pl.col("tp").shift(1).alias("tp_prev"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("tp") > pl.col("tp_prev"))
                .then(pl.col("mf"))
                .otherwise(0.0)
                .alias("pos_mf"),
                pl.when(pl.col("tp") < pl.col("tp_prev"))
                .then(pl.col("mf"))
                .otherwise(0.0)
                .alias("neg_mf"),
            ]
        )
        .with_columns(
            [
                pl.col("pos_mf").rolling_sum(window_size=window).alias("pos_mf_sum"),
                pl.col("neg_mf").rolling_sum(window_size=window).alias("neg_mf_sum"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("neg_mf_sum") == 0)
                .then(100.0)
                .otherwise(
                    100 - 100 / (1 + pl.col("pos_mf_sum") / pl.col("neg_mf_sum"))
                )
                .alias("mfi_series")
            ]
        )
    )

    # 2. Trích xuất giá trị cuối cùng
    last_row = df_mfi.tail(1).to_dicts()[0]
    mfi_val = last_row["mfi_series"]

    if mfi_val is None:
        return {"mfi_val": 50.0, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    # 3. Phân loại trạng thái
    if mfi_val > 80:
        trang_thai = "QUA_MUA"
        muc_do = "MANH" if mfi_val > 90 else "YEU"
    elif mfi_val < 20:
        trang_thai = "QUA_BAN"
        muc_do = "MANH" if mfi_val < 10 else "YEU"
    else:
        trang_thai = "BINH_THUONG"
        muc_do = "YEU"

    return {"mfi_val": mfi_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_awesome_oscillator(df, fast=5, slow=34):
    """Phân tích Awesome Oscillator bằng Polars: so sánh midprice SMA nhanh vs chậm."""
    # Null guard
    if df is None or df.height < slow:
        return {"ao_val": 0.0, "trang_thai": "TANG", "muc_do": "YEU"}

    # 1. Tính toán Awesome Oscillator
    df_ao = (
        df.with_columns([((pl.col("high") + pl.col("low")) / 2).alias("midprice")])
        .with_columns(
            [
                pl.col("midprice").rolling_mean(window_size=fast).alias("sma_fast"),
                pl.col("midprice").rolling_mean(window_size=slow).alias("sma_slow"),
            ]
        )
        .with_columns([(pl.col("sma_fast") - pl.col("sma_slow")).alias("ao_series")])
    )

    # 2. Trích xuất giá trị cuối cùng
    last_two = df_ao.tail(2).to_dicts()
    ao_val = last_two[-1]["ao_series"]

    if ao_val is None:
        return {"ao_val": 0.0, "trang_thai": "TANG", "muc_do": "YEU"}

    # 3. Phân loại trạng thái
    trang_thai = "TANG" if ao_val > 0 else "GIAM"

    # Mức độ: MANH nếu 2 bar liên tiếp cùng dấu VÀ |ao| đang tăng
    muc_do = "YEU"
    if len(last_two) == 2:
        ao_prev = last_two[-2]["ao_series"]
        if ao_prev is not None:
            same_sign = (ao_val > 0 and ao_prev > 0) or (ao_val < 0 and ao_prev < 0)
            increasing = abs(ao_val) > abs(ao_prev)
            if same_sign and increasing:
                muc_do = "MANH"

    return {"ao_val": ao_val, "trang_thai": trang_thai, "muc_do": muc_do}


def pt_tsi(df, long=25, short=13, signal=7):
    """Phân tích True Strength Index (TSI) qua double-smoothed momentum bằng pandas."""
    # Null guard
    if df is None or df.height < long + short:
        return {
            "tsi_val": 0.0,
            "signal_val": 0.0,
            "trang_thai": "TANG",
            "muc_do": "YEU",
        }

    # 1. Tính toán TSI qua pandas (chained EWM)
    pd_df = df.select(["close"]).to_pandas()
    momentum = pd_df["close"].diff()
    abs_momentum = momentum.abs()

    # Double smooth momentum
    ds_momentum = (
        momentum.ewm(span=short, adjust=False)
        .mean()
        .ewm(span=long, adjust=False)
        .mean()
    )
    # Double smooth |momentum|
    ds_abs_momentum = (
        abs_momentum.ewm(span=short, adjust=False)
        .mean()
        .ewm(span=long, adjust=False)
        .mean()
    )

    tsi_series = 100 * ds_momentum / ds_abs_momentum.replace(0, 1e-9)
    signal_series = tsi_series.ewm(span=signal, adjust=False).mean()

    tsi_val = tsi_series.iloc[-1]
    signal_val = signal_series.iloc[-1]
    tsi_prev = tsi_series.iloc[-2] if len(tsi_series) >= 2 else tsi_val
    sig_prev = signal_series.iloc[-2] if len(signal_series) >= 2 else signal_val

    import math

    if math.isnan(tsi_val) or math.isnan(signal_val):
        return {
            "tsi_val": 0.0,
            "signal_val": 0.0,
            "trang_thai": "TANG",
            "muc_do": "YEU",
        }

    # 2. Phân loại trạng thái
    crossed_above = (tsi_prev <= sig_prev) and (tsi_val > signal_val)
    crossed_below = (tsi_prev >= sig_prev) and (tsi_val < signal_val)

    if crossed_above:
        trang_thai = "CHEO_LEN"
    elif crossed_below:
        trang_thai = "CHEO_XUONG"
    elif tsi_val > 0:
        trang_thai = "TANG"
    else:
        trang_thai = "GIAM"

    muc_do = "MANH" if abs(tsi_val) > 25 else "YEU"

    return {
        "tsi_val": float(tsi_val),
        "signal_val": float(signal_val),
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_ultimate_oscillator(df, w1=7, w2=14, w3=28):
    """Phân tích Ultimate Oscillator bằng pandas: kết hợp 3 khung thời gian."""
    # Null guard
    if df is None or df.height < w3:
        return {"uo_val": 50.0, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    # 1. Tính toán Ultimate Oscillator qua pandas (rolling sums)
    pd_df = df.select(["high", "low", "close"]).to_pandas()
    prev_close = pd_df["close"].shift(1)

    bp = pd_df["close"] - pd_df[["low"]].join(prev_close.rename("pc")).min(axis=1)
    tr = pd_df[["high"]].join(prev_close.rename("pc")).max(axis=1) - pd_df[
        ["low"]
    ].join(prev_close.rename("pc")).min(axis=1)

    bp_sum1 = bp.rolling(w1).sum()
    bp_sum2 = bp.rolling(w2).sum()
    bp_sum3 = bp.rolling(w3).sum()
    tr_sum1 = tr.rolling(w1).sum()
    tr_sum2 = tr.rolling(w2).sum()
    tr_sum3 = tr.rolling(w3).sum()

    avg1 = bp_sum1 / tr_sum1.replace(0, 1e-9)
    avg2 = bp_sum2 / tr_sum2.replace(0, 1e-9)
    avg3 = bp_sum3 / tr_sum3.replace(0, 1e-9)

    uo_series = 100 * (4 * avg1 + 2 * avg2 + avg3) / (4 + 2 + 1)
    uo_val = uo_series.iloc[-1]

    import math

    if math.isnan(uo_val):
        return {"uo_val": 50.0, "trang_thai": "BINH_THUONG", "muc_do": "YEU"}

    # 2. Phân loại trạng thái
    if uo_val > 70:
        trang_thai = "QUA_MUA"
    elif uo_val < 30:
        trang_thai = "QUA_BAN"
    else:
        trang_thai = "BINH_THUONG"

    muc_do = "MANH" if uo_val > 60 or uo_val < 40 else "YEU"

    return {"uo_val": float(uo_val), "trang_thai": trang_thai, "muc_do": muc_do}
