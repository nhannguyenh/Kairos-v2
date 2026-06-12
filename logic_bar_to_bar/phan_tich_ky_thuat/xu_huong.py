"""XU HƯỚNG (Trend)
👉 Giá đang đi hướng nào?
- EMA, SMA
- MACD
- ADX
- Ichimoku
- SuperTrend
📌 Dùng để chọn phe BUY / SELL"""

import polars as pl


def pt_ema_trend(df, window=20):
    """Phân tích xu hướng dựa trên EMA bằng Polars: Hiệu suất cao."""

    # 1. Tính toán EMA trực tiếp trong DataFrame
    # Polars sử dụng ewm_mean (Exponential Weighted Moving Average)
    df_ema = df.select(
        [pl.col("close"), pl.col("close").ewm_mean(span=window).alias("ema_val")]
    )

    # 2. Trích xuất dòng cuối cùng
    last = df_ema.tail(1).to_dicts()[0]

    price_now = last["close"]
    ema_val = last["ema_val"]

    # Kiểm tra None (đề phòng dữ liệu quá ngắn)
    if ema_val is None:
        return {
            "ema_val": price_now,
            "price_now": price_now,
            "trang_thai": "KHÔNG_XÁC_ĐỊNH",
            "muc_do": "YẾU",
        }

    # 3. Logic phân loại trạng thái
    trang_thai = "TĂNG" if price_now > ema_val else "GIẢM"

    # Tính khoảng cách tương đối giữa giá và EMA
    diff_ratio = abs(price_now - ema_val) / (ema_val + 1e-9)
    muc_do = "TỐT" if diff_ratio > 0.005 else "YẾU"

    return {
        "ema_val": ema_val,
        "price_now": price_now,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_adx(df, window=28):
    """Phân tích lực xu hướng qua ADX bằng Polars Native."""
    if (
        df is None or df.height < window * 2
    ):  # ADX cần nhiều dữ liệu hơn cửa sổ để làm mượt
        return {"adx_val": 0, "trang_thai": "SIDEWAY", "muc_do": "THAP"}

    try:
        # 1. Tính toán True Range (TR) và Directional Movement (DM)
        df_calc = df.with_columns(
            [
                (
                    pl.max_horizontal(
                        pl.col("high") - pl.col("low"),
                        (pl.col("high") - pl.col("close").shift(1)).abs(),
                        (pl.col("low") - pl.col("close").shift(1)).abs(),
                    ).alias("tr")
                ),
                (pl.col("high") - pl.col("high").shift(1)).alias("up_move"),
                (pl.col("low").shift(1) - pl.col("low")).alias("down_move"),
            ]
        )

        # 2. Tính toán +DM, -DM và làm mượt bằng EWM (tương đương Wilder's)
        df_dm = df_calc.with_columns(
            [
                pl.when(
                    (pl.col("up_move") > pl.col("down_move")) & (pl.col("up_move") > 0)
                )
                .then(pl.col("up_move"))
                .otherwise(0)
                .alias("plus_dm"),
                pl.when(
                    (pl.col("down_move") > pl.col("up_move"))
                    & (pl.col("down_move") > 0)
                )
                .then(pl.col("down_move"))
                .otherwise(0)
                .alias("minus_dm"),
            ]
        ).with_columns(
            [
                pl.col("tr").ewm_mean(span=window, adjust=False).alias("atr_smooth"),
                pl.col("plus_dm")
                .ewm_mean(span=window, adjust=False)
                .alias("plus_di_smooth"),
                pl.col("minus_dm")
                .ewm_mean(span=window, adjust=False)
                .alias("minus_di_smooth"),
            ]
        )

        # 3. Tính DI+ , DI- và DX
        df_dx = df_dm.with_columns(
            [
                (100 * pl.col("plus_di_smooth") / (pl.col("atr_smooth") + 1e-9)).alias(
                    "plus_di"
                ),
                (100 * pl.col("minus_di_smooth") / (pl.col("atr_smooth") + 1e-9)).alias(
                    "minus_di"
                ),
            ]
        ).with_columns(
            [
                (
                    100
                    * (pl.col("plus_di") - pl.col("minus_di")).abs()
                    / (pl.col("plus_di") + pl.col("minus_di") + 1e-9)
                ).alias("dx")
            ]
        )

        # 4. Cuối cùng tính ADX bằng cách làm mượt DX
        df_adx = df_dx.with_columns(
            [pl.col("dx").ewm_mean(span=window, adjust=False).alias("adx")]
        )

        last_row = df_adx.tail(1).to_dicts()[0]
        adx_val = last_row["adx"]

        if adx_val is None:
            return {"adx_val": 0, "trang_thai": "SIDEWAY", "muc_do": "THAP"}

        trang_thai = "CO_XU_HUONG" if adx_val > 25 else "SIDEWAY"
        return {
            "adx_val": adx_val,
            "trang_thai": trang_thai,
            "muc_do": "MANH" if adx_val > 40 else "TRUNG_BINH",
        }
    except Exception:
        return {"adx_val": 0, "trang_thai": "SIDEWAY", "muc_do": "THAP"}


def pt_supertrend(df, window=10, multiplier=3.0):
    """Phân tích SuperTrend bằng Polars: Wilder's ATR + iterative flip logic."""
    if df is None or df.height < window * 2:
        return {"supertrend_val": 0.0, "trang_thai": "GIAM", "muc_do": "YEU"}

    try:
        multiplier = float(multiplier)
        window = int(window)

        # Chuyển sang pandas để xử lý vòng lặp đệ quy (iterative flip)
        pdf = df.select(["high", "low", "close"]).to_pandas()
        high = pdf["high"].values
        low = pdf["low"].values
        close = pdf["close"].values
        n = len(close)

        # 1. Tính ATR theo Wilder's Smoothing
        prev_close = pl.Series("pc", [close[0]] + list(close[:-1]))
        tr_vals = (
            df.with_columns(
                [
                    pl.max_horizontal(
                        pl.col("high") - pl.col("low"),
                        (pl.col("high") - prev_close).abs(),
                        (pl.col("low") - prev_close).abs(),
                    ).alias("tr")
                ]
            )
            .select("tr")
            .to_series()
            .to_numpy()
        )

        atr = [tr_vals[0]]
        for i in range(1, n):
            atr.append((atr[-1] * (window - 1) + tr_vals[i]) / window)
        atr = pl.Series(atr).to_numpy()

        # 2. Tính basic bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + multiplier * atr
        basic_lower = hl2 - multiplier * atr

        # 3. Vòng lặp đệ quy SuperTrend
        final_upper = [basic_upper[0]]
        final_lower = [basic_lower[0]]
        supertrend = [basic_upper[0]]
        in_uptrend = [True]

        for i in range(1, n):
            # Final Upper
            if basic_upper[i] < final_upper[-1] or close[i - 1] > final_upper[-1]:
                fu = basic_upper[i]
            else:
                fu = final_upper[-1]

            # Final Lower
            if basic_lower[i] > final_lower[-1] or close[i - 1] < final_lower[-1]:
                fl = basic_lower[i]
            else:
                fl = final_lower[-1]

            final_upper.append(fu)
            final_lower.append(fl)

            # Xu hướng
            if supertrend[-1] == final_upper[-2]:
                if close[i] > fu:
                    in_uptrend.append(True)
                    supertrend.append(fl)
                else:
                    in_uptrend.append(False)
                    supertrend.append(fu)
            else:
                if close[i] < fl:
                    in_uptrend.append(False)
                    supertrend.append(fu)
                else:
                    in_uptrend.append(True)
                    supertrend.append(fl)

        st_val = supertrend[-1]
        is_bull = bool(in_uptrend[-1])
        trang_thai = "TANG" if is_bull else "GIAM"

        # 4. Đánh giá mức độ dựa trên ADX đơn giản (EWM của DX)
        adx_val = 0.0
        try:
            adx_result = pt_adx(df, window=14)
            adx_val = adx_result.get("adx_val", 0.0) or 0.0
        except Exception:
            pass

        muc_do = "MANH" if adx_val > 25 else "YEU"

        return {
            "supertrend_val": float(st_val),
            "trang_thai": trang_thai,
            "muc_do": muc_do,
        }
    except Exception:
        return {"supertrend_val": 0.0, "trang_thai": "GIAM", "muc_do": "YEU"}


def pt_macd(df, fast=12, slow=26, signal=9):
    """Phân tích MACD trên nến đã đóng cuối cùng bằng Polars."""
    if df is None or df.height < slow + signal:
        return {
            "macd_val": 0.0,
            "signal_val": 0.0,
            "hist_val": 0.0,
            "trang_thai": "GIAM",
            "muc_do": "YEU",
        }

    try:
        fast = int(fast)
        slow = int(slow)
        signal = int(signal)

        # 1. Tính EMA fast, slow, rồi MACD line
        df_calc = (
            df.with_columns(
                [
                    pl.col("close").ewm_mean(span=fast, adjust=False).alias("ema_fast"),
                    pl.col("close").ewm_mean(span=slow, adjust=False).alias("ema_slow"),
                ]
            )
            .with_columns(
                [(pl.col("ema_fast") - pl.col("ema_slow")).alias("macd_line")]
            )
            .with_columns(
                [
                    pl.col("macd_line")
                    .ewm_mean(span=signal, adjust=False)
                    .alias("signal_line")
                ]
            )
            .with_columns(
                [(pl.col("macd_line") - pl.col("signal_line")).alias("hist_line")]
            )
        )

        # 2. Lấy 2 dòng cuối để phát hiện crossover
        tail2 = df_calc.tail(2).to_dicts()
        if len(tail2) < 2:
            return {
                "macd_val": 0.0,
                "signal_val": 0.0,
                "hist_val": 0.0,
                "trang_thai": "GIAM",
                "muc_do": "YEU",
            }

        prev = tail2[0]
        last = tail2[1]

        macd_val = last["macd_line"]
        signal_val = last["signal_line"]
        hist_val = last["hist_line"]
        prev_hist = prev["hist_line"]

        if macd_val is None or signal_val is None or hist_val is None:
            return {
                "macd_val": 0.0,
                "signal_val": 0.0,
                "hist_val": 0.0,
                "trang_thai": "GIAM",
                "muc_do": "YEU",
            }

        # 3. Phân loại trạng thái
        if prev_hist is not None and prev_hist <= 0 and hist_val > 0:
            trang_thai = "CHEO_LEN"
        elif prev_hist is not None and prev_hist >= 0 and hist_val < 0:
            trang_thai = "CHEO_XUONG"
        elif hist_val > 0:
            trang_thai = "TANG"
        else:
            trang_thai = "GIAM"

        muc_do = "MANH" if abs(hist_val) > abs(macd_val) * 0.1 else "YEU"

        return {
            "macd_val": float(macd_val),
            "signal_val": float(signal_val),
            "hist_val": float(hist_val),
            "trang_thai": trang_thai,
            "muc_do": muc_do,
        }
    except Exception:
        return {
            "macd_val": 0.0,
            "signal_val": 0.0,
            "hist_val": 0.0,
            "trang_thai": "GIAM",
            "muc_do": "YEU",
        }


def pt_sma(df, window=50):
    """Phân tích Simple Moving Average (SMA) xu hướng bằng Polars."""
    if df is None or df.height < window:
        return {"sma_val": 0.0, "price_now": 0.0, "trang_thai": "DUOI", "muc_do": "GAN"}

    try:
        window = int(window)

        # 1. Tính SMA
        df_calc = df.with_columns(
            [pl.col("close").rolling_mean(window_size=window).alias("sma_val")]
        )

        last = df_calc.tail(1).to_dicts()[0]
        price_now = last["close"]
        sma_val = last["sma_val"]

        if sma_val is None:
            return {
                "sma_val": price_now,
                "price_now": price_now,
                "trang_thai": "DUOI",
                "muc_do": "GAN",
            }

        # 2. Phân loại trạng thái
        trang_thai = "TREN" if price_now > sma_val else "DUOI"
        dist_ratio = abs(price_now - sma_val) / (sma_val + 1e-9)
        muc_do = "XA" if dist_ratio > 0.02 else "GAN"

        return {
            "sma_val": float(sma_val),
            "price_now": float(price_now),
            "trang_thai": trang_thai,
            "muc_do": muc_do,
        }
    except Exception:
        return {"sma_val": 0.0, "price_now": 0.0, "trang_thai": "DUOI", "muc_do": "GAN"}


def pt_aroon(df, window=25):
    """Phân tích Aroon Indicator bằng Polars."""
    if df is None or df.height < window + 1:
        return {
            "aroon_up": 50.0,
            "aroon_down": 50.0,
            "aroon_osc": 0.0,
            "trang_thai": "DI_NGANG",
            "muc_do": "YEU",
        }

    try:
        window = int(window)

        # 1. Tính Aroon qua rolling argmax/argmin (pandas cho rolling custom function)
        pdf = df.select(["high", "low"]).to_pandas()
        high = pdf["high"]
        low = pdf["low"]

        # rolling(window+1): cần window+1 điểm để có window khoảng
        aroon_up = (
            high.rolling(window + 1).apply(lambda x: x.argmax(), raw=True)
            / window
            * 100
        )
        aroon_down = (
            low.rolling(window + 1).apply(lambda x: x.argmin(), raw=True) / window * 100
        )

        up_val = float(aroon_up.iloc[-1]) if not aroon_up.isna().iloc[-1] else 50.0
        down_val = (
            float(aroon_down.iloc[-1]) if not aroon_down.isna().iloc[-1] else 50.0
        )
        osc_val = up_val - down_val

        # 2. Phân loại trạng thái
        if up_val > 70 and down_val < 30:
            trang_thai = "TANG"
        elif down_val > 70 and up_val < 30:
            trang_thai = "GIAM"
        else:
            trang_thai = "DI_NGANG"

        # Mức độ: MANH nếu một trong hai > 70, ngược lại YEU
        muc_do = "MANH" if (up_val > 70 or down_val > 70) else "YEU"

        return {
            "aroon_up": up_val,
            "aroon_down": down_val,
            "aroon_osc": osc_val,
            "trang_thai": trang_thai,
            "muc_do": muc_do,
        }
    except Exception:
        return {
            "aroon_up": 50.0,
            "aroon_down": 50.0,
            "aroon_osc": 0.0,
            "trang_thai": "DI_NGANG",
            "muc_do": "YEU",
        }


def pt_ichimoku(df, tenkan=9, kijun=26, senkou_b=52):
    """Phân tích Ichimoku Cloud (đơn giản hóa) bằng Polars."""
    if df is None or df.height < senkou_b:
        return {
            "tenkan": 0.0,
            "kijun": 0.0,
            "senkou_a": 0.0,
            "senkou_b": 0.0,
            "trang_thai": "TRONG_MAY",
            "muc_do": "YEU",
        }

    try:
        tenkan = int(tenkan)
        kijun = int(kijun)
        senkou_b = int(senkou_b)

        # Dùng pandas cho rolling_max / rolling_min
        pdf = df.select(["high", "low", "close"]).to_pandas()
        high = pdf["high"]
        low = pdf["low"]

        tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
        kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
        senkou_b_s = (high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2

        t_val = float(tenkan_sen.iloc[-1]) if not tenkan_sen.isna().iloc[-1] else 0.0
        k_val = float(kijun_sen.iloc[-1]) if not kijun_sen.isna().iloc[-1] else 0.0
        sb_val = float(senkou_b_s.iloc[-1]) if not senkou_b_s.isna().iloc[-1] else 0.0
        sa_val = (t_val + k_val) / 2

        close_val = float(pdf["close"].iloc[-1])

        # Trạng thái so với mây
        cloud_top = max(sa_val, sb_val)
        cloud_bottom = min(sa_val, sb_val)
        if close_val > cloud_top:
            trang_thai = "TREN_MAY"
        elif close_val < cloud_bottom:
            trang_thai = "DUOI_MAY"
        else:
            trang_thai = "TRONG_MAY"

        # Mức độ: MANH nếu độ dày mây > 0.5% của giá đóng
        cloud_thickness = abs(sa_val - sb_val)
        muc_do = "MANH" if (cloud_thickness / (close_val + 1e-9)) > 0.005 else "YEU"

        return {
            "tenkan": t_val,
            "kijun": k_val,
            "senkou_a": sa_val,
            "senkou_b": sb_val,
            "trang_thai": trang_thai,
            "muc_do": muc_do,
        }
    except Exception:
        return {
            "tenkan": 0.0,
            "kijun": 0.0,
            "senkou_a": 0.0,
            "senkou_b": 0.0,
            "trang_thai": "TRONG_MAY",
            "muc_do": "YEU",
        }


def pt_psar(df, af_start=0.02, af_step=0.02, af_max=0.2):
    """Phân tích Parabolic SAR theo thuật toán Wilder's iterative."""
    if df is None or df.height < 20:
        return {"psar_val": 0.0, "trang_thai": "GIAM", "muc_do": "YEU"}

    try:
        af_start = float(af_start)
        af_step = float(af_step)
        af_max = float(af_max)

        pdf = df.select(["high", "low", "close"]).to_pandas()
        high = pdf["high"].values
        low = pdf["low"].values
        close = pdf["close"].values
        n = len(close)

        # Khởi tạo: bắt đầu với xu hướng tăng
        bull = True
        af = af_start
        ep = low[0]  # extreme point
        psar = high[0]  # SAR ban đầu

        for i in range(1, n):
            prev_psar = psar

            if bull:
                psar = prev_psar + af * (ep - prev_psar)
                psar = min(psar, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
                if low[i] < psar:
                    # Đảo chiều sang GIAM
                    bull = False
                    psar = ep
                    ep = low[i]
                    af = af_start
                else:
                    if high[i] > ep:
                        ep = high[i]
                        af = min(af + af_step, af_max)
            else:
                psar = prev_psar + af * (ep - prev_psar)
                psar = max(psar, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
                if high[i] > psar:
                    # Đảo chiều sang TANG
                    bull = True
                    psar = ep
                    ep = high[i]
                    af = af_start
                else:
                    if low[i] < ep:
                        ep = low[i]
                        af = min(af + af_step, af_max)

        psar_val = float(psar)
        close_last = float(close[-1])

        trang_thai = "TANG" if close_last > psar_val else "GIAM"
        dist_ratio = abs(close_last - psar_val) / (close_last + 1e-9)
        muc_do = "MANH" if dist_ratio > 0.01 else "YEU"

        return {"psar_val": psar_val, "trang_thai": trang_thai, "muc_do": muc_do}
    except Exception:
        return {"psar_val": 0.0, "trang_thai": "GIAM", "muc_do": "YEU"}


def pt_vortex(df, window=14):
    """Phân tích Vortex Indicator bằng Polars / pandas."""
    if df is None or df.height < window + 1:
        return {"vi_plus": 1.0, "vi_minus": 1.0, "trang_thai": "TANG", "muc_do": "YEU"}

    try:
        window = int(window)

        pdf = df.select(["high", "low", "close"]).to_pandas()
        high = pdf["high"]
        low = pdf["low"]
        close = pdf["close"]
        prev_close = close.shift(1)
        prev_high = high.shift(1)
        prev_low = low.shift(1)

        # True Range
        tr = (
            (high - low)
            .abs()
            .combine((high - prev_close).abs(), max)
            .combine((low - prev_close).abs(), max)
        )

        # Vortex Movement
        vm_plus = (high - prev_low).abs()
        vm_minus = (low - prev_high).abs()

        # Rolling sums
        sum_tr = tr.rolling(window).sum()
        sum_vm_plus = vm_plus.rolling(window).sum()
        sum_vm_minus = vm_minus.rolling(window).sum()

        vi_plus_s = sum_vm_plus / (sum_tr + 1e-9)
        vi_minus_s = sum_vm_minus / (sum_tr + 1e-9)

        vi_plus_val = (
            float(vi_plus_s.iloc[-1]) if not vi_plus_s.isna().iloc[-1] else 1.0
        )
        vi_minus_val = (
            float(vi_minus_s.iloc[-1]) if not vi_minus_s.isna().iloc[-1] else 1.0
        )

        trang_thai = "TANG" if vi_plus_val > vi_minus_val else "GIAM"
        muc_do = "MANH" if abs(vi_plus_val - vi_minus_val) > 0.1 else "YEU"

        return {
            "vi_plus": vi_plus_val,
            "vi_minus": vi_minus_val,
            "trang_thai": trang_thai,
            "muc_do": muc_do,
        }
    except Exception:
        return {"vi_plus": 1.0, "vi_minus": 1.0, "trang_thai": "TANG", "muc_do": "YEU"}
