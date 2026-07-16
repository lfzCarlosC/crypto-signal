from typing import Optional
import numpy as np
import pandas as pd

def is_pattern_too_compressed(a_idx: Optional[int], b_idx: Optional[int], c_idx: Optional[int]) -> bool:
    """
    检查谐波形态中的 B、C 点是否与 A 点过于紧邻（连续三个索引：x, x+1, x+2）。

    参数:
        a_idx: A点的索引
        b_idx: B点的索引
        c_idx: C点的索引

    返回:
        bool: 如果是紧邻连续点返回 True，否则返回 False
    """
    if a_idx is None or b_idx is None or c_idx is None:
        return False

    # 核心几何逻辑：如果 B 紧跟 A，C 紧跟 B，说明极为紧凑，缺乏波段震荡
    return (b_idx == a_idx + 1) and (c_idx == b_idx + 1)

def _wilder_rma(series: pd.Series, period: int) -> pd.Series:
    """
    Wilder's RMA，与 Pine Script 的 ta.rma() 完全一致：
        rma := na(rma[1]) ? ta.sma(source, length) : (source - rma[1]) / length + rma[1]
    即：前 period 根用简单平均(SMA)作为"种子"，之后再按 alpha=1/period 递推平滑。

    注意：pandas 的 series.ewm(alpha=1/period, adjust=False) 并不等价于此——
    它是直接从第一个数据点开始递推（种子=第一个值本身），而不是用 SMA 做种子。
    在历史K线足够长（几百根以上）时两者会收敛到同一个值，但在只取
    几十到一百根K线的短窗口下，种子误差还没衰减完就被截断了，
    会导致算出的 RSI 与 TradingView 上看到的对不上（period 越大偏差越明显）。
    """
    values = series.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return pd.Series(out, index=series.index)

    seed = np.nanmean(values[:period])
    out[period - 1] = seed
    alpha = 1.0 / period
    prev = seed
    for i in range(period, n):
        prev = prev + alpha * (values[i] - prev)
        out[i] = prev
    return pd.Series(out, index=series.index)

def calc_rsi(close, period=7):
    """
    与 TradingView Pine Script `ta.rsi(src, len)` 严格对齐的 RSI 计算。
    要求传入的 close 序列足够长（建议至少 period 的 8~10 倍，即
    period=14 建议 >=100根，period=28 建议 >=200根），否则 Wilder 平滑
    的种子误差无法充分衰减，算出的最新值会偏离 TradingView 的真实值。
    """
    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _wilder_rma(gain, period)
    avg_loss = _wilder_rma(loss, period)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # avg_loss 为 0 且 avg_gain > 0 时（持续上涨无回撤），RSI 应为 100
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    # avg_gain、avg_loss 都为 0（价格完全不变）时，RSI 定义为 50
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi