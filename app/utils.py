from typing import Optional
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

def calc_rsi(close, period=7):
    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))