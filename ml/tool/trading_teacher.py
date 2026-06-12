import polars as pl
import numpy as np


class TradingTeacher:
    def __init__(self):
        # Bộ nhớ riêng biệt cho mỗi thực thể (Instance)
        self.last_state = 0
        self.change_count = 0

    def detect_regime(self, df_5m=None, df_15m=None, df_1h=None, df_4h=None):
        """
        Hedge Fund Level Regime Detection.
        Logic: Swing Liquidity, MTF, Express Lane cho Fast States.
        """

        def _calc_features(df_in):
            """Tính toán các chỉ báo kỹ thuật từ DataFrame OHLCV; trả về dict dòng cuối."""
            if df_in is None or df_in.height < 120:
                return None
            df = df_in
            try:
                # ================= 1. Cấu trúc Swing & Biến động =================
                df = df.with_columns(
                    [
                        pl.col("close").diff().alias("diff"),
                        pl.col("high").rolling_max(20).shift(1).alias("prev_high"),
                        pl.col("low").rolling_min(20).shift(1).alias("prev_low"),
                        pl.max_horizontal(
                            [
                                (pl.col("high") - pl.col("low")),
                                (pl.col("high") - pl.col("close").shift(1)).abs(),
                                (pl.col("low") - pl.col("close").shift(1)).abs(),
                            ]
                        ).alias("tr"),
                    ]
                )

                # ================= 2. Volatility & Trend =================
                df = df.with_columns(
                    [
                        pl.col("tr").ewm_mean(span=14, adjust=False).alias("atr"),
                        pl.col("close").ewm_mean(span=50, adjust=False).alias("ema_50"),
                    ]
                ).with_columns(
                    [
                        (pl.col("atr") / (pl.col("close") + 1e-9)).alias("ATRn"),
                        (
                            (pl.col("high") - pl.col("low")) / (pl.col("atr") + 1e-9)
                        ).alias("SpreadATR"),
                        (
                            (pl.col("ema_50") - pl.col("ema_50").shift(5))
                            / (pl.col("ema_50").shift(5) + 1e-9)
                        ).alias("S"),
                    ]
                )

                # RSI & ADX (Wilder's Smoothing)
                df = (
                    df.with_columns(
                        [
                            pl.when(pl.col("diff") > 0)
                            .then(pl.col("diff"))
                            .otherwise(0)
                            .ewm_mean(span=14, adjust=False)
                            .alias("gain"),
                            pl.when(pl.col("diff") < 0)
                            .then(pl.col("diff").abs())
                            .otherwise(0)
                            .ewm_mean(span=14, adjust=False)
                            .alias("loss"),
                        ]
                    )
                    .with_columns(
                        [
                            (
                                100
                                - (
                                    100
                                    / (1 + (pl.col("gain") / (pl.col("loss") + 1e-9)))
                                )
                            ).alias("RSI")
                        ]
                    )
                    .with_columns(
                        [(pl.col("RSI") - pl.col("RSI").shift(3)).alias("RSIslope")]
                    )
                )

                df = (
                    df.with_columns(
                        [
                            (pl.col("high") - pl.col("high").shift(1)).alias("up_move"),
                            (pl.col("low").shift(1) - pl.col("low")).alias("down_move"),
                        ]
                    )
                    .with_columns(
                        [
                            pl.when(
                                (pl.col("up_move") > pl.col("down_move"))
                                & (pl.col("up_move") > 0)
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
                    )
                    .with_columns(
                        [
                            (
                                pl.col("plus_dm").ewm_mean(span=27, adjust=False)
                                / (pl.col("tr").ewm_mean(span=27, adjust=False) + 1e-9)
                            ).alias("di_plus"),
                            (
                                pl.col("minus_dm").ewm_mean(span=27, adjust=False)
                                / (pl.col("tr").ewm_mean(span=27, adjust=False) + 1e-9)
                            ).alias("di_minus"),
                        ]
                    )
                    .with_columns(
                        [
                            (
                                100
                                * (
                                    (pl.col("di_plus") - pl.col("di_minus")).abs()
                                    / (pl.col("di_plus") + pl.col("di_minus") + 1e-9)
                                )
                            )
                            .ewm_mean(span=27, adjust=False)
                            .alias("ADX")
                        ]
                    )
                )

                # ================= 3. Nén & Squeeze =================
                df = (
                    df.with_columns(
                        [
                            pl.col("close").rolling_mean(20).alias("bb_mid"),
                            pl.col("close").rolling_std(20).alias("bb_std"),
                            pl.col("close")
                            .ewm_mean(span=20, adjust=False)
                            .alias("ema_20"),
                        ]
                    )
                    .with_columns(
                        [
                            (pl.col("bb_mid") + 2 * pl.col("bb_std")).alias("bb_upper"),
                            (pl.col("bb_mid") - 2 * pl.col("bb_std")).alias("bb_lower"),
                        ]
                    )
                    .with_columns(
                        [
                            pl.when(
                                (
                                    pl.col("bb_upper")
                                    < (pl.col("ema_20") + 1.5 * pl.col("atr"))
                                )
                                & (
                                    pl.col("bb_lower")
                                    > (pl.col("ema_20") - 1.5 * pl.col("atr"))
                                )
                            )
                            .then(1.0)
                            .otherwise(0.0)
                            .alias("SQZ"),
                            (
                                (pl.col("close") - pl.col("close").shift(10)).abs()
                                / (pl.col("diff").abs().rolling_sum(10) + 1e-9)
                            ).alias("ER"),
                        ]
                    )
                )

                # Choppiness
                df = df.with_columns(
                    [
                        pl.col("tr").rolling_sum(14).alias("tr_sum"),
                        pl.col("high").rolling_max(14).alias("high_max"),
                        pl.col("low").rolling_min(14).alias("low_min"),
                    ]
                ).with_columns(
                    [
                        (
                            100
                            * (
                                pl.col("tr_sum")
                                / (pl.col("high_max") - pl.col("low_min") + 1e-9)
                            ).log10()
                            / np.log10(14)
                        ).alias("CHOP")
                    ]
                )

                # ================= 4. Volume & Wick Structure =================
                df = df.with_columns(
                    [
                        pl.col("volume").rolling_mean(20).alias("vol_sma"),
                        pl.col("volume").rolling_std(20).alias("vol_std"),
                        (
                            (pl.col("close") * pl.col("volume")).rolling_sum(100)
                            / (pl.col("volume").rolling_sum(100) + 1e-9)
                        ).alias("vwap"),
                        pl.max_horizontal("open", "close").alias("body_top"),
                        pl.min_horizontal("open", "close").alias("body_bottom"),
                        (pl.col("high") - pl.col("low") + 1e-9).alias("hl_range"),
                    ]
                ).with_columns(
                    [
                        (
                            (pl.col("volume") - pl.col("vol_sma"))
                            / (pl.col("vol_std") + 1e-9)
                        ).alias("VOLz"),
                        (
                            (pl.col("close") - pl.col("vwap")) / (pl.col("atr") + 1e-9)
                        ).alias("VWAPd"),
                        (
                            (pl.col("high") - pl.col("body_top")) / pl.col("hl_range")
                        ).alias("WickUpProp"),
                        (
                            (pl.col("body_bottom") - pl.col("low")) / pl.col("hl_range")
                        ).alias("WickDnProp"),
                        pl.col("ATRn").rolling_mean(100).alias("ATRn_avg100"),
                    ]
                )
                return df.tail(1).to_dicts()[0]
            except Exception as e:
                return None

        # MTF Calculations
        c_h4 = _calc_features(df_4h) if df_4h is not None else _calc_features(df_1h)
        c_h1 = _calc_features(df_1h)
        c_m15 = _calc_features(df_15m)
        c_m5 = _calc_features(df_5m)

        if not all([c_h1, c_m15, c_m5]):
            return self.last_state, 0.0

        confidence = 0.6
        scores = {k: 0.0 for k in range(8)}

        # ================= KHỐI LUẬT GẮN NHÃN =================
        sweep_up = (
            (c_m5["high"] > c_m5["prev_high"])
            and (c_m5["close"] < c_m5["prev_high"])
            and (c_m5["WickUpProp"] > 0.40)
        )
        sweep_down = (
            (c_m5["low"] < c_m5["prev_low"])
            and (c_m5["close"] > c_m5["prev_low"])
            and (c_m5["WickDnProp"] > 0.40)
        )

        if (sweep_up or sweep_down) and c_m5["VOLz"] > 2.0:
            scores[7] = 100.0
        else:
            is_dead = (c_h1["VOLz"] < -1.2) and (
                c_h1["ATRn"] < (c_h1["ATRn_avg100"] * 0.65)
            )
            if is_dead:
                scores[0] = 100.0
            else:
                if (c_h1["SQZ"] == 1.0 or c_m15["SQZ"] == 1.0) and (
                    c_m15["CHOP"] > 50 or c_h1["ER"] < 0.35
                ):
                    scores[1] += 60
                if (
                    c_h1["ADX"] >= 28
                    and np.sign(c_h4["S"]) == np.sign(c_h1["S"]) == np.sign(c_m15["S"])
                    and c_m15["ER"] > 0.38
                    and c_h1["CHOP"] < 45
                    and abs(c_h1["VWAPd"]) < 2.2
                ):
                    scores[3] += 65
                if (
                    abs(c_m15["S"]) > 0.0015
                    and (c_m15["ER"] > 0.32)
                    and (10 <= c_h1["ADX"] < 25)
                ):
                    scores[2] += 55
                if abs(c_h1["VWAPd"]) > 2.0 and (c_h1["RSI"] > 72 or c_h1["RSI"] < 28):
                    scores[4] += 60
                if (
                    abs(c_h1["VWAPd"]) > 1.5
                    and abs(c_m15["RSIslope"]) > 4
                    and c_h1["ADX"] < 28
                    and c_m15["ER"] < 0.45
                ):
                    scores[5] += 62
                if c_h1["ER"] < 0.35 and c_h1["ADX"] < 22 and c_m15["CHOP"] > 48:
                    scores[6] += 50
                    scores[2] *= 0.5
                    scores[3] *= 0.5

        # ================= QUÁN TÍNH & SOFTMAX =================
        scores[self.last_state] += max(
            4.0, 10.0 * confidence if "confidence" in locals() else 6.0
        )
        max_s = max(scores.values())
        exps = {k: np.exp(v - max_s) for k, v in scores.items()}
        total_exp = sum(exps.values())
        probs = {k: v / total_exp for k, v in exps.items()}

        raw_state = max(probs, key=probs.get)
        confidence = probs[raw_state]

        top2 = sorted(probs.values(), reverse=True)[:2]
        if confidence < 0.60 or (top2[0] - top2[1]) < 0.08:
            raw_state = self.last_state

        # ================= EXPRESS LANE PATCH =================
        fast_states = [4, 7]
        if raw_state in fast_states:
            self.last_state = raw_state
            self.change_count = 0
        else:
            if raw_state != self.last_state:
                self.change_count += 1
            else:
                self.change_count = 0

            if self.change_count >= 3:
                self.last_state = raw_state
                self.change_count = 0

        return self.last_state, float(confidence)

