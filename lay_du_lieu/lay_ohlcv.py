"""
lay_du_lieu/lay_ohlcv.py – Lấy và chuẩn bị dữ liệu OHLCV
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3 chức năng chính:
  1. lay_du_lieu_nen()          – fetch 8 khung thời gian (1m→1d) cho bot realtime/demo
  2. tai_du_lieu_lich_su()      – tải toàn bộ lịch sử 1m từ Binance cho backtest
  3. chuan_bi_du_lieu_da_khung_vectorized() – build 8 khung từ 1m gốc cho vectorized backtest

Dùng Polars thay Pandas để xử lý nhanh hơn ~3-5x trên dataset lớn.
"""

import polars as pl
from thuc_thi_lenh.bo_may_thuc_thi import quan_ly_san
from utils.log import logger
import ccxt
import sys
import time
from datetime import datetime, timedelta


def gop_nen(df, timeframe_dich):
    """Gộp nến 1m thành khung lớn hơn bằng Polars group_by_dynamic (không lookahead)."""
    if df is None or df.is_empty():
        return None

    rule = timeframe_dich.lower().replace("min", "m")

    try:
        df_res = (
            df.group_by_dynamic(
                "timestamp",
                every=rule,
                closed="left",  # Tương đương closed='left'
                label="left",  # Tương đương label='left'
                start_by="window",  # Giúp khớp mốc thời gian chẵn (ví dụ 0h, 4h, 8h...)
            )
            .agg(
                [
                    pl.col("open").first(),
                    pl.col("high").max(),
                    pl.col("low").min(),
                    pl.col("close").last(),
                    pl.col("volume").sum(),
                ]
            )
            .drop_nulls()
        )

        # Kiểm tra độ dài tối thiểu
        return df_res if len(df_res) >= 25 else None

    except Exception as e:
        logger.error(f"Lỗi gộp nến {timeframe_dich}: {e}")
        return None


def chuan_bi_du_lieu_da_khung(df_goc, current_time, limit_lookback=43200):
    """
    Cắt DataFrame đến current_time rồi gộp ra 8 khung thời gian (dùng cho backtest bar-to-bar).
    Trả về list [df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d].
    """
    MAX_OUTPUT = 300
    df_den_hien_tai = df_goc.filter(pl.col("timestamp") <= current_time)

    if df_den_hien_tai.is_empty():
        return None
    df_working = df_den_hien_tai.tail(limit_lookback)

    timeframes = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }

    results = []
    for label, interval in timeframes.items():
        if interval == "1m":
            df_res = df_working
        else:
            df_res = gop_nen(df_working, interval)
        results.append(df_res.tail(MAX_OUTPUT))
    return results


def fetch_raw(exchange, symbol, timeframe, limit=1000):
    """Fetch OHLCV thô từ sàn qua CCXT, trả về Polars DataFrame với timestamp đã parse."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        # Define the schema upfront for better performance
        schema = {
            "timestamp": pl.Int64,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        }
        # Initialize DataFrame and convert timestamp in one go
        df = pl.DataFrame(ohlcv, schema=list(schema.keys()), orient="row").with_columns(
            [pl.from_epoch("timestamp", time_unit="ms")]
        )
        return df
    except Exception as e:
        logger.error(f"Lỗi fetch {symbol} {timeframe}: {e}")
        return None


def lay_du_lieu_nen(
    ten_san, symbol
):  # df_1m có 300 nến, df_3m có 100 nến, df_5m có 300 nến, df_15m có 100 nến, df_30m có 300 nến, df_1h có 150 nến, df_4h có 300 nến, df_1d có 50 nến
    """Fetch 8 khung thời gian đồng thời cho một symbol từ sàn chỉ định."""
    exchange = quan_ly_san.lay_san(ten_san)
    df_1m = df_3m = df_5m = df_15m = df_30m = df_1h = df_4h = df_1d = None
    if not exchange:
        return df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d

    df_1m = fetch_raw(exchange, symbol, "1m", limit=300)
    if df_1m is not None:
        df_3m = gop_nen(df_1m, "3m")  # 100

    df_5m = fetch_raw(exchange, symbol, "5m", limit=300)
    if df_5m is not None:
        df_15m = gop_nen(df_5m, "15m")  # 100

    df_30m = fetch_raw(exchange, symbol, "30m", limit=300)
    if df_30m is not None:
        df_1h = gop_nen(df_30m, "1h")  # 150

    df_4h = fetch_raw(exchange, symbol, "4h", limit=300)
    if df_4h is not None:
        df_1d = gop_nen(df_4h, "1d")  # 50

    return df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d


def tai_du_lieu_lich_su(symbol, start_str, end_str):
    """
    Tải toàn bộ nến 1m từ Binance theo khoảng ngày (YYYY-MM-DD).
    Tự động thêm 30 ngày buffer trước start để indicator warm-up không bị null.
    """
    try:
        start_obj = datetime.strptime(start_str, "%Y-%m-%d")
        since_obj = start_obj - timedelta(days=30)
        since_str = since_obj.strftime("%Y-%m-%d")
        logger.info(
            f"Đang tải dữ liệu {symbol} từ {since_str} (Buffer 30 ngày) đến {end_str}..."
        )
    except ValueError:
        logger.error(
            f"Định dạng ngày {start_str} không hợp lệ. Vui lòng dùng YYYY-MM-DD"
        )
        return pl.DataFrame()

    exchange = ccxt.binance()

    try:
        since = exchange.parse8601(f"{since_str} 00:00:00")
        end_ts = exchange.parse8601(f"{end_str} 23:59:59")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, microsecond=0
        )
    except Exception as e:
        logger.error(f"Lỗi parse ngày tháng: {e}")
        return pl.DataFrame()

    all_ohlcv = []
    limit = 1000

    while since < end_ts:
        try:
            data = exchange.fetch_ohlcv(symbol, "1m", since=since, limit=limit)
            if not data:
                break

            last_timestamp = data[-1][0]
            if last_timestamp <= since:
                break

            all_ohlcv.extend(data)
            since = last_timestamp + 60_000
        except Exception as e:
            logger.error(f"Lỗi tải data: {e}")
            time.sleep(2)

    if not all_ohlcv:
        return pl.DataFrame()

    schema = ["timestamp", "open", "high", "low", "close", "volume"]
    df = pl.DataFrame(all_ohlcv, schema=schema, orient="row")

    df = (
        df.with_columns([pl.from_epoch("timestamp", time_unit="ms")])
        .unique(subset=["timestamp"], keep="first")
        .filter(
            # Lọc từ 00:00:00 ngày buffer đến đúng 23:59:59 ngày kết thúc
            (pl.col("timestamp") >= since_obj)
            & (pl.col("timestamp") <= end_dt)
        )
        .sort("timestamp")
    )

    return df


def chuan_bi_du_lieu_da_khung_vectorized(df_goc):
    """Build 8 khung thời gian từ 1m gốc theo cách vectorized (dùng cho ML training & backtest hàng loạt)."""
    df_1m = df_goc
    df_3m = gop_nen_vector(df_goc, "3min")
    df_5m = gop_nen_vector(df_goc, "5min")
    df_15m = gop_nen_vector(df_goc, "15min")
    df_30m = gop_nen_vector(df_goc, "30min")
    df_1h = gop_nen_vector(df_goc, "1h")
    df_4h = gop_nen_vector(df_goc, "4h")
    df_1d = gop_nen_vector(df_goc, "1d")

    return [
        df_1m.to_pandas(),
        df_3m.to_pandas(),
        df_5m.to_pandas(),
        df_15m.to_pandas(),
        df_30m.to_pandas(),
        df_1h.to_pandas(),
        df_4h.to_pandas(),
        df_1d.to_pandas(),
    ]


def gop_nen_vector(df, timeframe_dich):
    """Gộp nến theo cách vectorized (live OHLCV tích lũy trong nến), giữ nguyên số dòng gốc."""
    rule = (
        timeframe_dich.lower()
        .replace("min", "m")
        .replace("minute", "m")
        .replace("hour", "h")
        .replace("day", "d")
    )

    try:
        df = df.sort("timestamp")

        truncate_col = pl.col("timestamp").dt.truncate(rule)

        df_built = df.with_columns(
            [
                pl.col("open").first().over(truncate_col).alias("open_live"),
                pl.col("high").cum_max().over(truncate_col).alias("high_live"),
                pl.col("low").cum_min().over(truncate_col).alias("low_live"),
                pl.col("volume").cum_sum().over(truncate_col).alias("volume_live"),
            ]
        )

        df_res = df_built.group_by_dynamic(
            "timestamp", every="1m", closed="left", label="left"
        ).agg(
            [
                pl.col("open_live").last().alias("open"),
                pl.col("high_live").last().alias("high"),
                pl.col("low_live").last().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume_live").last().alias("volume"),
            ]
        )

        df_final = df.select("timestamp").join_asof(
            df_res, on="timestamp", strategy="backward"
        )

        return df_final

    except Exception as e:
        print(f"Lỗi gop nen Live {timeframe_dich}: {e}")
        return None
