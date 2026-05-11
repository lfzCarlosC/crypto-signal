"""
Harmonic + SMC Scanner  (v2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
新增功能：
  1. 入场窗口过滤 — D点出现后3根K线内，价格触及
       多单：D点K线低点的上方1/3处（low + range×1/3）
       空单：D点K线高点的下方1/3处（high - range×1/3）
     才生成信号（避免追高/追低，等回踩入场）

  2. Double Bottom / Double Top 检测（1:1 复刻 Pine Script）
       zigzagdir 序列：
         DB: dirs[-1]==-1(LL)  dirs[-2]==1   dirs[-3]==-2(LowLow)
         DT: dirs[-1]==1(HH)   dirs[-2]==-1  dirs[-3]==2 (HiHi)
       riskPerReward = |value - llvalue| / (|value-llvalue| + |value-lvalue|) × 100

  3. TD Sequential 计数（9、13计数）
       DB两个底之间跨越的bar范围内，检测是否存在 TD8~TD13

  4. 综合 conf 逻辑
       DB独立计1分；DB + 两底间存在TD8~13 额外再计1分
       format_signal 打印全部 conf 因素明细

可调参数 (HARMONIC_* 前缀)：
  HARMONIC_ERROR_PCT    = 10
  HARMONIC_ZZ_LENGTH    = 2
  HARMONIC_ZZ_SIZE      = 40
  HARMONIC_PRZ_BUFFER   = 0.003
  HARMONIC_SL_BUFFER    = 0.002
  HARMONIC_MIN_RR       = 2.0
  HARMONIC_SWEEP_BARS   = 5
  HARMONIC_ENTRY_BARS   = 3     # D点后等待入场的最大K线数
  HARMONIC_DB_MAX_RRP   = 40    # DB/DT 的最大 riskPerReward%（同 Pine MaxRiskPerReward）
"""

import time
import datetime
import sys

try:
    import ccxt.async_support as ccxt_async
    import ccxt
    import pandas as pd
    import numpy as np
except ImportError:
    print("pip install ccxt pandas numpy")
    sys.exit(1)

# ── 配置 ────────────────────────────────────────
EXCHANGE_ID   = "bitget"
SYMBOL        = "BTC/USDT"
TIMEFRAMES    = ["30m", "1h", "4h", "6h"]
SCAN_INTERVAL = 60 * 15

TF_FETCH_LIMIT = {
    "15m": 220, "30m": 250, "1h": 300,
    "4h": 350,  "6h": 350,  "12h": 300, "1d": 200
}

# 谐波参数
HARMONIC_ERROR_PCT  = 10
HARMONIC_ZZ_LENGTH  = 2
HARMONIC_ZZ_SIZE    = 40
HARMONIC_PRZ_BUFFER = 0.003
HARMONIC_SL_BUFFER  = 0.002
HARMONIC_MIN_RR     = 1.05
HARMONIC_SWEEP_BARS = 5
HARMONIC_ENTRY_BARS = 3      # D点后允许等待入场的最大K线数
HARMONIC_DB_MAX_RRP = 40     # DB/DT riskPerReward 上限（%）
HARMONIC_TP1_CD_RATIO = 1.13
HARMONIC_TP2_CD_RATIO = 1.618
HARMONIC_STOP_RR      = 1.2  # 用 TP1 反推初始止损，默认 1:1.2
HARMONIC_TP1_STOP_FRAC = 0.5 # 额外止损约束：TP1距离的 0.5 位置
ENTRY_D_GAP_FILTER_TFS = {"30m", "1h"}
ENTRY_D_GAP_MAX_PCT    = 0.005  # 0.5%

# 颜色
RESET   = "\033[0m";  RED    = "\033[91m"; GREEN  = "\033[92m"
YELLOW  = "\033[93m"; CYAN   = "\033[96m"; BOLD   = "\033[1m";  DIM    = "\033[2m"
MAGENTA = "\033[95m"

# ── 数据获取 ─────────────────────────────────────
def fetch_ohlcv(exchange, symbol, timeframe, limit=200):
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not raw: return None
        df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df.astype({c: float for c in ["open","high","low","close","volume"]})
    except Exception:
        return None


def log_scan_skip(msg: str):
    return

# ── 基础指标 ─────────────────────────────────────
def calc_atr(df, period=14):
    hl  = df["high"] - df["low"]
    hpc = (df["high"] - df["close"].shift()).abs()
    lpc = (df["low"]  - df["close"].shift()).abs()
    return pd.concat([hl, hpc, lpc], axis=1).max(axis=1).ewm(span=period, adjust=False).mean()

# ── ZigZag ───────────────────────────────────────
import numpy as np


def get_pine_zigzag(df, length=2, deviation=0, max_size=40):
    high, low = df["high"].values, df["low"].values
    n = len(high)

    zz_indices, zz_prices, zz_dirs, zz_ratios = [], [], [], []
    dir_state = 0

    def _find_prev_line_start_price() -> float | None:
        # Pine get_edir() 用的是最近一条 zigzag line 的起点 y1
        # 对应到 pivot 序列，就是倒数第二个 pivot 价格
        if len(zz_prices) >= 2:
            return zz_prices[-2]
        return None

    def _find_prev_same_side_price(direction: int, include_last: bool = False):
        end = len(zz_dirs) if include_last else len(zz_dirs) - 1
        for k in range(end - 1, -1, -1):
            if (zz_dirs[k] > 0 and direction > 0) or (zz_dirs[k] < 0 and direction < 0):
                return zz_prices[k]
        return None

    def _calc_e_dir(direction: int, val: float) -> int:
        last_pivot = _find_prev_line_start_price()
        if last_pivot is None:
            return direction
        return (2 if direction * val > direction * last_pivot else 1) * direction

    def _calc_ratio_for_last() -> float:
        if len(zz_prices) < 3:
            return 0.0
        current_len = abs(zz_prices[-1] - zz_prices[-2])
        last_len = abs(zz_prices[-2] - zz_prices[-3])
        return round(current_len / last_len, 3) if last_len > 1e-8 else 0.0

    def _recalc_last_dir() -> None:
        if not zz_prices or not zz_dirs:
            return
        direction = 1 if zz_dirs[-1] > 0 else -1
        val = zz_prices[-1]
        prev_same_side = _find_prev_same_side_price(direction)
        if prev_same_side is None:
            zz_dirs[-1] = 2 * direction
        else:
            zz_dirs[-1] = (2 if direction * val > direction * prev_same_side else 1) * direction

    for i in range(n):
        # 1. 严格对齐 Pine Script 的 pivots(length) 逻辑
        # ta.highestbars(high, length) == 0 表示当前 Bar 是最近 length 根里的最高
        start_idx = max(0, i - length + 1)
        high_window = high[start_idx: i + 1]
        low_window = low[start_idx: i + 1]
        is_ph = (np.argmax(high_window) == len(high_window) - 1)
        is_pl = (np.argmin(low_window) == len(low_window) - 1)

        # 2. pivots(length) 的 dir 逻辑
        prev_dir = dir_state
        current_dir = prev_dir
        if is_pl and not is_ph:
            current_dir = -1
        elif is_ph and not is_pl:
            current_dir = 1
        dir_state = current_dir
        dir_changed = (current_dir != prev_dir)

        # 3. 如果当前 Bar 是一个有效的 Pivot 点
        if (is_ph and current_dir == 1) or (is_pl and current_dir == -1):
            val = high[i] if current_dir == 1 else low[i]

            if not zz_prices:
                # 初始第一个点
                zz_indices.append(i)
                zz_prices.append(val)
                zz_dirs.append(2 * current_dir)
                zz_ratios.append(0.0)
                continue

            if dir_changed:
                # Pine add_to_zigzag(..., dirchanged, ...)：方向变化时新增一段
                y1 = zz_prices[-1]
                if abs(y1 - val) * 100 / max(abs(y1), 1e-8) >= deviation:
                    zz_indices.append(i)
                    zz_prices.append(val)
                    zz_dirs.append(_calc_e_dir(current_dir, val))
                    zz_ratios.append(_calc_ratio_for_last())
                    _recalc_last_dir()
            else:
                # 方向未变化时，只更新当前这段的更极端端点
                if (current_dir == 1 and val > zz_prices[-1]) or (current_dir == -1 and val < zz_prices[-1]):
                    zz_indices[-1] = i
                    zz_prices[-1] = val
                    zz_ratios[-1] = _calc_ratio_for_last()
                    _recalc_last_dir()

    # 对应 Pine 的 max_array_size 截断
    if len(zz_prices) > max_size:
        zz_indices = zz_indices[-max_size:]
        zz_prices = zz_prices[-max_size:]
        zz_dirs = zz_dirs[-max_size:]
        zz_ratios = zz_ratios[-max_size:]

    return zz_indices, zz_prices, zz_dirs, zz_ratios


def is_last_pivot_confirmed(df: pd.DataFrame, zz_indices: list[int], zz_dirs: list[int]) -> bool:
    """
    判断最后一个 pivot 是否已经被后续完整 K 线确认。

    当前规则简化为：
      - 最后一个 pivot 后面只要有一根完整 K 线
      - 并且该 K 线颜色发生反转
      - 就视为 pivot 已确认
    """
    if df is None or df.empty or not zz_indices or not zz_dirs:
        return False

    pivot_idx = int(zz_indices[-1])
    if pivot_idx + 1 >= len(df):
        return False

    pivot_bar = df.iloc[pivot_idx]
    n1 = df.iloc[pivot_idx + 1]
    pivot_open = float(pivot_bar["open"])
    pivot_close = float(pivot_bar["close"])
    n1_open = float(n1["open"])
    n1_close = float(n1["close"])
    pivot_is_bull = pivot_close > pivot_open
    pivot_is_bear = pivot_close < pivot_open
    n1_is_bull = n1_close > n1_open
    n1_is_bear = n1_close < n1_open

    # 只要 D 点后面那根 K 线颜色与 D 点本身不同，就视为确认。
    if pivot_is_bull and n1_is_bear:
        return True
    if pivot_is_bear and n1_is_bull:
        return True
    return False


# ── 谐波比例 ─────────────────────────────────────
def safe_ratio(numer, denom):
    return abs(numer) / abs(denom) if abs(denom) > 1e-8 else 0


def harmonic_ratios(p: list) -> tuple:
    x, a, b, c, d = p[0], p[1], p[2], p[3], p[4]
    xa_len = a - x
    ab_len = b - a
    bc_len = c - b
    xab = safe_ratio(b - a, xa_len)
    abc = safe_ratio(c - b, ab_len)
    bcd = safe_ratio(d - c, bc_len)
    xad = safe_ratio(d - a, xa_len)
    return round(xab, 4), round(abc, 4), round(bcd, 4), round(xad, 4)


def abcd_ratios(p: list, indices: list | None = None) -> tuple:
    a, b, c, d = p[0], p[1], p[2], p[3]
    ab_len = b - a
    bc_len = c - b
    abc = safe_ratio(c - b, ab_len)
    bcd = safe_ratio(d - c, bc_len)
    price_ratio = safe_ratio(d - c, b - a)
    time_ratio = 0.0
    if indices is not None and len(indices) >= 4:
        ab_time = abs(int(indices[-3]) - int(indices[-4]))
        cd_time = abs(int(indices[-1]) - int(indices[-2]))
        time_ratio = safe_ratio(cd_time, ab_time)
    return round(abc, 4), round(bcd, 4), round(price_ratio, 4), round(time_ratio, 4)


def _in(v: float, lo: float, hi: float, err: float) -> bool:
    e = err / 100
    return lo * (1 - e) <= v <= hi * (1 + e)


def detect_harmonic(prices: list, indices: list | None = None, err_pct: float = 10):
    """
    1:1 复刻 Pine Script 的 wm_patterns 判定逻辑
    err_pct: 对应 Pine 的误差百分比 (如 10 代表 10%)
    """
    if len(prices) < 5:
        return None

    p5 = list(prices[-5:])
    x, a, b, c, d = p5

    # 计算比例 (对应 Pine 的 xabRatio, abcRatio, bcdRatio)
    # xab = B点回调XA的比例, abc = C点回调AB的比例, bcd = D点回调BC的比例
    xab, abc, bcd, xad = harmonic_ratios(p5)
    is_bull = (a > d)

    # 对应 Pine 的误差计算方式
    err_min = 1 - (err_pct / 100)
    err_max = 1 + (err_pct / 100)

    # 1:1 复刻 Pine 的 B点区间限制逻辑
    max_p1 = max(x, a);
    max_p2 = max(c, d)
    min_p1 = min(x, a);
    min_p2 = min(c, d)
    high_point = min(max_p1, max_p2)
    low_point = max(min_p1, min_p2)
    b_in_range = (low_point < b < high_point)

    matched = None

    # 辅助函数：判断值是否在 Pine 的误差区间内
    def _check(val, target, e_min=err_min, e_max=err_max):
        return val >= target * e_min and val <= target * e_max

    # 辅助函数：判断值是否在指定的范围区间内（带误差）
    def _check_range(val, target_low, target_high, e_min=err_min, e_max=err_max):
        return val >= target_low * e_min and val <= target_high * e_max

    if b_in_range:
        # 1. Gartley
        if (_check(xab, 0.618) and
                _check_range(abc, 0.382, 0.886) and
                (_check_range(bcd, 1.272, 1.618) or _check(xad, 0.786))):
            matched = "Gartley"

        # 2. Crab
        elif (_check_range(xab, 0.382, 0.618) and
              _check_range(abc, 0.382, 0.886) and
              (_check_range(bcd, 2.24, 3.618) or _check(xad, 1.618))):
            matched = "Crab"

        # 3. Deep Crab
        elif (_check(xab, 0.886) and
              _check_range(abc, 0.382, 0.886) and
              (_check_range(bcd, 2.00, 3.618) or _check(xad, 1.618))):
            matched = "DeepCrab"

        # 4. Bat (修复了你图片中 0.631 被识别的问题)
        elif (_check_range(xab, 0.382, 0.50) and
              _check_range(abc, 0.382, 0.886) and
              (_check_range(bcd, 1.618, 2.618) or _check(xad, 0.886))):
            matched = "Bat"

        # 5. Butterfly
        elif (_check(xab, 0.786) and
              _check_range(abc, 0.382, 0.886) and
              (_check_range(bcd, 1.618, 2.618) or _check_range(xad, 1.272, 1.618))):
            matched = "Butterfly"

        # 6. Shark (Shark 要求三者必须同时满足，无 OR 逻辑)
        elif (_check_range(abc, 1.13, 1.618) and
              _check_range(bcd, 1.618, 2.24) and
              _check_range(xad, 0.886, 1.13)):
            matched = "Shark"

        # 7. Cypher
        elif (_check_range(xab, 0.382, 0.618) and
              _check_range(abc, 1.13, 1.414) and
              (_check_range(bcd, 1.272, 2.00) or _check(xad, 0.786))):
            matched = "Cypher"

    # 特殊形态 (3-Drive, 5-0)
    if matched is None:
        if len(prices) >= 6:
            p6 = list(prices[-6:])
            # Pine: yxaRatio = array.get(zigzagratios, 4)
            yxa = safe_ratio(abs(p6[2] - p6[1]), abs(p6[1] - p6[0]))

            # 3-Drive
            if (_check(yxa, 0.618) and _check_range(xab, 1.27, 1.618) and
                    _check(abc, 0.618) and _check_range(bcd, 1.27, 1.618)):
                matched = "3Drive"

            # 5-0
            elif (_check_range(xab, 1.13, 1.618) and
                  _check_range(abc, 1.618, 2.24) and
                  _check(bcd, 0.5)):
                matched = "FiveZero"

    if matched is None:
        return None
    return matched, is_bull


def detect_abcd_pattern(prices: list, indices: list | None = None, err_pct: float = 10):
    """
    1:1 对齐 pine.txt 的 calculate_abcd()。
    输入使用最后 4 个确认点 [A, B, C, D]。
    """
    if len(prices) < 4:
        return None

    p4 = list(prices[-4:])
    idx4 = list(indices[-4:]) if indices is not None and len(indices) >= 4 else None
    a, b, c, d = p4
    abc, bcd, price_ratio, time_ratio = abcd_ratios(p4, idx4)

    err_min = 1 - (err_pct / 100)
    err_max = 1 + (err_pct / 100)

    abcd_direction = (
        (a < b and a < c and c < b and c < d and a < d and b < d)
        or
        (a > b and a > c and c > b and c > d and a > d and b > d)
    )
    if not abcd_direction:
        return None

    # 上升结构完成于高位 => bearish / SHORT
    # 下降结构完成于低位 => bullish / LONG
    is_bull = not (a < b and a < c and c < b and c < d and a < d and b < d)

    if (0.618 * err_min <= abc <= 0.786 * err_max and
            1.272 * err_min <= bcd <= 1.618 * err_max):
        return "ABCD", is_bull
    if (err_min <= time_ratio <= err_max and
            err_min <= price_ratio <= err_max):
        return "AB=CD", is_bull
    if (1.272 * err_min <= price_ratio <= 1.618 * err_max and
            0.618 * err_min <= abc <= 0.786 * err_max):
        return "ABCD Ext", is_bull
    return None


# ── PRZ质量评分 ───────────────────────────────────
def score_prz_quality(prices: list, pattern_name: str, err: float) -> tuple:
    if pattern_name in {"ABCD", "AB=CD", "ABCD Ext"}:
        if len(prices) < 4:
            return 0, []
        abc, bcd, price_ratio, time_ratio = abcd_ratios(prices[-4:])
        strict = err / 2
        score = 0
        detail = []
        if pattern_name == "AB=CD":
            checks = [("price", price_ratio, 1.0), ("time", time_ratio, 1.0)]
        elif pattern_name == "ABCD Ext":
            checks = [("abc", abc, 0.702), ("price", price_ratio, 1.445)]
        else:
            checks = [("abc", abc, 0.702), ("bcd", bcd, 1.445)]
        for key, actual, ideal in checks:
            dev = abs(actual - ideal) / ideal * 100 if ideal > 0 else 100
            if dev < strict:
                score += 2
                detail.append(f"{key.upper()}={actual:.3f}(★★)")
            elif dev < err:
                score += 1
                detail.append(f"{key.upper()}={actual:.3f}(★)")
            else:
                detail.append(f"{key.upper()}={actual:.3f}(偏差{dev:.1f}%)")
        return score, detail

    if len(prices) < 5: return 0, []
    xab, abc, bcd, xad = harmonic_ratios(prices)
    targets = {
        "Gartley":   {"xab": 0.618, "xad": 0.786},
        "Bat":       {"xab": 0.450, "xad": 0.886},
        "Butterfly": {"xab": 0.786, "xad": 1.414},
        "Crab":      {"xab": 0.500, "xad": 1.618},
        "DeepCrab":  {"xab": 0.886, "xad": 1.618},
        "Cypher":    {"xab": 0.500, "xad": 0.786},
    }
    t = targets.get(pattern_name, {})
    if not t: return 2, [f"未知形态{pattern_name}"]
    strict = err / 2
    score = 0; detail = []
    for key, actual in [("xab", xab), ("xad", xad)]:
        ideal = t.get(key, 0)
        dev   = abs(actual - ideal) / ideal * 100 if ideal > 0 else 100
        if dev < strict:
            score += 2; detail.append(f"{key.upper()}={actual:.3f}(★★)")
        elif dev < err:
            score += 1; detail.append(f"{key.upper()}={actual:.3f}(★)")
        else:
            detail.append(f"{key.upper()}={actual:.3f}(偏差{dev:.1f}%)")
    return score, detail


# ══════════════════════════════════════════════════════
# ── Double Bottom / Double Top（1:1 Pine Script 复刻）──
# ══════════════════════════════════════════════════════
def detect_double_pattern(prices, dirs, bars_indices, max_risk_per_reward=40.0):
    """
    1:1 复刻 Pine Script 的 Double Top / Double Bottom 检测逻辑

    逻辑依据 (Pine Script 翻译):
    - Double Top:  highLow == 1 (当前顶) 且 llhighLow == 2 (前顶更高) 且 lhighLow == -1 (中间底)
    - Double Bottom: highLow == -1 (当前底) 且 llhighLow == -2 (前底更低) 且 lhighLow == 1 (中间顶)
    - 风险比例: riskPerReward = risk * 100 / (risk + reward) < MaxRiskPerReward
    """
    # Pine Script 逻辑中至少需要回溯 3 段 ZigZag 路径 (对应索引 1, 2, 3)
    if len(prices) < 4:
        return {"type": None}

    # --- 1. 获取索引并判断跨度 (你的“土办法”) ---
    # idx_d: 当前 D 点在 K 线图中的位置
    # idx_b: 左侧第一个底/顶（B点）在 K 线图中的位置
    idx_d = bars_indices[-1]
    idx_b = bars_indices[-3]

    # 计算两个极点之间的 Bar 数量（包含两端）
    bars_between = abs(idx_d - idx_b )

    # 如果两个点靠得太近（< 5 根 Bar），视为无效或同一个震荡区，直接抛弃
    if bars_between < 5:
        return {"type": None}

    # --- 1. 获取价格 (对应 Pine 的 line.get_y2) ---
    # value: 当前 D 点; lvalue: 颈线(回撤点); llvalue: 左侧第一个顶/底
    value = prices[-1]
    lvalue = prices[-2]
    llvalue = prices[-3]

    # --- 2. 获取方向 (对应 Pine 的 zigzagdir) ---
    # dirs 的定义需满足: 2/-2 为极值突破(HH/LL), 1/-1 为未突破(LH/HL)
    highLow = dirs[-1]
    lhighLow = dirs[-2]
    llhighLow = dirs[-3]

    # --- 3. 计算风险回报比 (riskPerReward) ---
    # Pine 公式: risk = |D - B1|, reward = |D - Neckline|
    risk = abs(value - llvalue)
    reward = abs(value - lvalue)

    total_movement = risk + reward
    if total_movement == 0:
        return {"type": None}

    # 严格按照 Pine 的 riskPerReward 算法
    riskPerReward = (risk * 100.0) / total_movement

    # --- 4. 核心逻辑匹配 ---

    # Double Top (双顶) 判定:
    # 当前是顶(1), 前一个是底(-1), 再前一个是更高顶(2)
    if highLow == 1 and llhighLow == 2 and lhighLow == -1 and riskPerReward < max_risk_per_reward:
        return {
            "type": "DT",
            "rrp": round(riskPerReward, 2),
            "d_bar_idx": bars_indices[-1],
            "bottom1_zz_offset": -3,  # 对应 llvalue 的位置，用于 TD 扫描范围
            "bottom2_zz_offset": -1  # 对应 value 的位置
        }

    # Double Bottom (双底) 判定:
    # 当前是底(-1), 前一个是顶(1), 再前一个是更低底(-2)
    if highLow == -1 and llhighLow == -2 and lhighLow == 1 and riskPerReward < max_risk_per_reward:
        return {
            "type": "DB",
            "rrp": round(riskPerReward, 2),
            "d_bar_idx": bars_indices[-1],
            "bottom1_zz_offset": -3,
            "bottom2_zz_offset": -1
        }

    return {"type": None}

# ══════════════════════════════════════════════════════
# ── TD Sequential 计数 ────────────────────────────────
# ══════════════════════════════════════════════════════
def calc_td_sequential(df: pd.DataFrame) -> list:
    """
    TD Setup 计数（9-bar setup）：
      看涨 Setup：close[i] < close[i-4]，连续≥9根为完成setup
      看跌 Setup：close[i] > close[i-4]，连续≥9根为完成setup

    返回每根 bar 的 TD 计数列表（正数=看涨，负数=看跌，0=无）。
    计数在 1~13 之间滚动（超过13重置）。
    """
    cl  = df["close"].values
    n   = len(cl)
    td  = [0] * n
    cnt = 0  # 正=看涨，负=看跌

    for i in range(4, n):
        if cl[i] < cl[i - 4]:        # 看涨条件
            if cnt <= 0:
                cnt = 1              # 重置/开始新的看涨计数
            else:
                cnt += 1
                if cnt > 13: cnt = 1  # 超过13，重置
        elif cl[i] > cl[i - 4]:      # 看跌条件
            if cnt >= 0:
                cnt = -1
            else:
                cnt -= 1
                if cnt < -13: cnt = -1
        else:
            cnt = 0                  # 持平不计数
        td[i] = cnt

    return td


def check_td_between_bottoms(df: pd.DataFrame,
                              bar_idx1: int, bar_idx2: int) -> dict:
    """
    检测两个底（bar_idx1 到 bar_idx2）之间是否存在 TD 8~13 计数。

    返回：
      {
        "found": bool,
        "td_values": [满足条件的td计数列表],
        "bar_range": (bar_idx1, bar_idx2)
      }
    """
    if bar_idx1 >= bar_idx2 or bar_idx2 >= len(df):
        return {"found": False, "td_values": [], "bar_range": (bar_idx1, bar_idx2)}

    td_series = calc_td_sequential(df)
    # 在两个底之间的bar范围内（含两端）查找 |td| in [8,13]
    found_tds = []
    for i in range(bar_idx1, bar_idx2 + 1):
        v = td_series[i]
        if 8 <= abs(v) <= 13:
            found_tds.append(v)

    return {
        "found": len(found_tds) > 0,
        "td_values": found_tds,
        "bar_range": (bar_idx1, bar_idx2)
    }


# ══════════════════════════════════════════════════════
# ── 入场窗口过滤 ──────────────────────────────────────
# ══════════════════════════════════════════════════════
def find_smc_structures(df: pd.DataFrame, is_bull: bool, d_idx: int):
    """寻找左侧最近的 FVG 缺口和 OB 块"""
    hi = df['high'].values
    lo = df['low'].values

    fvg_target = None
    # 1. 寻找最近的 FVG (Fair Value Gap) 作为 TP1 参考
    # 往回找 100 根 K 线
    for i in range(d_idx - 1, max(1, d_idx - 100), -1):
        if is_bull:
            # 看涨：找上方空头失衡区 (上一根L > 下一根H)
            if lo[i - 1] > hi[i + 1]:
                fvg_target = (lo[i - 1] + hi[i + 1]) / 2.0
                break
        else:
            # 看空：找下方多头失衡区 (上一根H < 下一根L)
            if hi[i - 1] < lo[i + 1]:
                fvg_target = (hi[i - 1] + lo[i + 1]) / 2.0
                break

    # 2. 寻找 OB (Order Block) 作为止损参考
    # 逻辑：取 D 点前后 2 根 K 线内最极端的影线位置
    lookback = df.iloc[max(0, d_idx - 2): d_idx + 1]
    if is_bull:
        ob_sl = lookback['low'].min() * (1 - 0.001)  # 低点下方 0.1%
    else:
        ob_sl = lookback['high'].max() * (1 + 0.001)  # 高点上方 0.1%

    return fvg_target, ob_sl

def check_entry_window(df: pd.DataFrame, d_bar_idx: int,
                       is_bull: bool, entry_bars: int = 3,
                       c_price: float = None) -> dict:
    """
    Fail-fast 入场逻辑（索罗斯灵魂：小止损大盈利）：

      入场价  = D→C 段的 0.786 位置（从D点往C方向走0.786）
               多单：entry = D点low + D→C × 0.786
               空单：entry = D点high - D→C × 0.786
    止损/止盈 = 由外层根据谐波目标与 RR 反推，这里只负责给出入场参考位

    c_price: C点价格，用于精确计算CD段长度。未传入时退化为D点K线range。
    """
    hi = df["high"].values
    lo = df["low"].values

    d_high  = hi[d_bar_idx]
    d_low   = lo[d_bar_idx]
    d_range = d_high - d_low

    # CD 段长度：优先用传入的 c_price
    if c_price is not None:
        cd_len = abs(c_price - (d_low if is_bull else d_high))
    else:
        cd_len = d_range  # 退化：用 D点K线range

    ENTRY_FRAC = 0.786
    if is_bull:
        entry_price = d_low + cd_len * ENTRY_FRAC
    else:
        entry_price = d_high - cd_len * ENTRY_FRAC

    return {
        "triggered":   True,
        "entry_price": float(entry_price),
        "trigger_bar": d_bar_idx,
        "d_range":     float(d_range),
        "cd_len":      float(cd_len),
        "d_high":      float(d_high),
        "d_low":       float(d_low),
    }


# ── 溢价/折价区 ───────────────────────────────────
def get_zone(price, df_range_n=60, df=None):
    if df is None: return "equilibrium", 50.0
    hi  = df["high"].iloc[-df_range_n:].max()
    lo  = df["low"].iloc[-df_range_n:].min()
    rng = hi - lo
    if rng <= 0: return "equilibrium", 50.0
    pct  = (price - lo) / rng * 100
    zone = "premium" if pct > 55 else "discount" if pct < 45 else "equilibrium"
    return zone, round(pct, 1)


# ── SMC确认A：流动性扫荡 ──────────────────────────
def check_sweep_at_d(df, d_price: float, is_bull: bool, atr: float, n=5) -> bool:
    tail = df.iloc[-n:]
    buf  = atr * 0.3
    if is_bull:
        swept  = (tail["low"] < d_price - buf).any()
        closed = (tail["close"].iloc[-1] > d_price - buf)
        return bool(swept and closed)
    else:
        swept  = (tail["high"] > d_price + buf).any()
        closed = (tail["close"].iloc[-1] < d_price + buf)
        return bool(swept and closed)


# ── SMC确认B：OB重叠 ─────────────────────────────
def find_obs_near_d(df, d_price: float, atr: float) -> list:
    obs = []
    hi  = df["high"].values
    lo  = df["low"].values
    op  = df["open"].values
    cl  = df["close"].values
    win = atr * 1.5
    n   = len(df)
    for i in range(2, n - 2):
        body_next = abs(cl[i+1] - op[i+1])
        avg_body  = np.mean([abs(cl[k]-op[k]) for k in range(max(0,i-5),i)]) + 1e-10
        if cl[i] < op[i] and cl[i+1] > op[i+1] and body_next > avg_body * 1.4:
            ob_mid = (hi[i] + lo[i]) / 2
            if abs(ob_mid - d_price) <= win:
                if not any(cl[k] < lo[i] for k in range(i+1, n)):
                    obs.append({"type":"bullish","top":hi[i],"bottom":lo[i],"mid":ob_mid})
        if cl[i] > op[i] and cl[i+1] < op[i+1] and body_next > avg_body * 1.4:
            ob_mid = (hi[i] + lo[i]) / 2
            if abs(ob_mid - d_price) <= win:
                if not any(cl[k] > hi[i] for k in range(i+1, n)):
                    obs.append({"type":"bearish","top":hi[i],"bottom":lo[i],"mid":ob_mid})
    return obs


# ── SMC确认C：FVG位移 ────────────────────────────
def check_fvg_after_d(df, d_bar_idx: int, is_bull: bool) -> bool:
    start = max(d_bar_idx + 1, len(df) - 8)
    hi = df["high"].values; lo = df["low"].values
    op = df["open"].values; cl = df["close"].values
    n  = len(df)
    for i in range(start + 1, min(n - 1, start + 6)):
        body = abs(cl[i] - op[i])
        rng  = hi[i] - lo[i] + 1e-10
        if body / rng < 0.40: continue
        if is_bull     and lo[i-1] > hi[i+1]: return True
        if not is_bull and hi[i-1] < lo[i+1]: return True
    return False


# ── SMC确认D：CHoCH ──────────────────────────────
def check_choch_at_d(df: pd.DataFrame, d_bar_idx: int,
                     is_bull: bool, lookback: int = 8) -> bool:
    n     = len(df)
    start = max(d_bar_idx, n - lookback)
    if start >= n - 3: return False
    hi = df["high"].values; lo = df["low"].values
    if is_bull:
        lows_after = lo[start + 1: n]
        return bool(len(lows_after) >= 2 and lows_after[-1] > lows_after[0])
    else:
        highs_after = hi[start + 1: n]
        return bool(len(highs_after) >= 2 and highs_after[-1] < highs_after[0])


def find_smc_targets(df: pd.DataFrame, is_bull: bool, d_idx: int):
    """
    寻找左侧最近的 FVG 和 未缓解的 OB 作为 TP/SL 参考
    """
    hi = df['high'].values
    lo = df['low'].values
    cl = df['close'].values

    tp_fvg = None
    tp_ob = None

    # 向左回溯寻找最近的失衡区 (FVG)
    # 扫描最近的 50 根 K 线
    for i in range(d_idx - 1, max(0, d_idx - 50), -1):
        if is_bull:  # 看涨单，找上方卖方失衡 (Bearish FVG)
            # 逻辑：前一根的低点 > 后一根的高点 (中间留下缺口)
            if lo[i - 1] > hi[i + 1] and tp_fvg is None:
                tp_fvg = (lo[i - 1] + hi[i + 1]) / 2.0  # 取 FVG 中轴
        else:  # 看空单，找下方买方失衡 (Bullish FVG)
            if hi[i - 1] < lo[i + 1] and tp_fvg is None:
                tp_fvg = (hi[i - 1] + lo[i + 1]) / 2.0

    # 寻找左侧未被触碰的 OB (Order Block)
    # 这里简化逻辑：寻找导致强力波动的最后一根反转 K 线
    for i in range(d_idx - 5, max(0, d_idx - 100), -1):
        if is_bull:
            # 寻找上方阻力 OB：一波下跌前的最后一根阳线
            if cl[i] > df['open'].iloc[i] and hi[i] > hi[d_idx]:
                tp_ob = hi[i]
                break
        else:
            if cl[i] < df['open'].iloc[i] and lo[i] < lo[d_idx]:
                tp_ob = lo[i]
                break

    return tp_fvg, tp_ob

# ── 质量评估 ───────────────────────────────────────
def evaluate_harmonic_quality(df, d_bar_idx, is_bull, a_price, x_price, a_idx, x_idx, c_idx):
    """
    保留原有接口的评分函数
    返回：q_score (总分), acc_s (碎度), exp_s (顿度), lev_s (撬棍)

    特殊返回值：q_score = -1 表示形态无效（钝角过滤），调用方应跳过该信号。
    钝角判定：
      ① xad > 1.0 且 CD时间跨度 > XA时间跨度 × 2.5（D点超延伸且拖沓）
      ② CD时间跨度 > XA时间跨度 × 3.0（纯时间上的过度延伸）
    """
    d_bar = df.iloc[d_bar_idx]
    d_price = d_bar['low'] if is_bull else d_bar['high']
    atr = df['atr'].iloc[d_bar_idx] if 'atr' in df.columns else (d_bar['high'] - d_bar['low'])

    # ── 钝角过滤（Obtuse Angle Filter）──────────────────────────────
    xa_bars = abs(a_idx - x_idx) + 1
    xa_height = abs(a_price - x_price) + 1e-10
    # xad 比例（由外部传入的价格计算，这里近似用 d_price 和 a/x 重算）
    xad_ratio = abs(d_price - a_price) / xa_height
    cd_bars = abs(d_bar_idx - c_idx) + 1

    # 条件①：xad超延伸（D超越X点方向）且时间拖沓
    is_xad_obtuse = (xad_ratio > 1.0 and cd_bars > xa_bars * 2.5)
    # 条件②：纯时间过度延伸
    is_time_obtuse = (cd_bars > xa_bars * 3.0)

    if is_xad_obtuse or is_time_obtuse:
        return -1, 0, 0, 0   # q_score=-1 为无效标志

    # --- 1. 顿度因子 (AXD/CDX 角度对比 - exp_s) ---
    # 计算左角 A (AXD) 钝度：越宽越钝
    xa_width = abs(a_idx - x_idx) + 1
    xa_height = abs(a_price - x_price) + 1e-10
    a_dullness = xa_width / xa_height

    # 计算右角 D (CDX) 钝度
    ad_width = abs(d_bar_idx - a_idx) + 1
    ad_height = abs(d_price - a_price) + 1e-10
    d_dullness = ad_width / ad_height

    # 顿度对比：左钝 / 右锐。比值越大代表右边越尖。
    angle_ratio = a_dullness / (d_dullness + 1e-10)
    exp_s = min(angle_ratio * 0.75, 1.5)  # 映射为爆发/顿度得分

    # --- 2. 碎度因子 (CD 端纠缠度 - acc_s) ---
    cd_segment = df.iloc[min(a_idx, d_bar_idx): max(a_idx, d_bar_idx) + 1]
    num_bars = len(cd_segment)

    acc_s = 0  # 对应碎度
    max_body_ratio = 0

    if num_bars > 1:
        overlaps = []
        for i in range(1, num_bars):
            prev = cd_segment.iloc[i - 1]
            curr = cd_segment.iloc[i]

            # 记录最大实体用于动态惩罚
            body_len = abs(curr['close'] - curr['open'])
            max_body_ratio = max(max_body_ratio, body_len / (atr + 1e-10))

            # 计算相邻 K 线重叠
            inter_min = max(prev['low'], curr['low'])
            inter_max = min(prev['high'], curr['high'])
            overlap_range = max(0, inter_max - inter_min)
            curr_range = curr['high'] - curr['low'] + 1e-10
            overlaps.append(overlap_range / curr_range)

        avg_overlap = sum(overlaps) / len(overlaps)
        acc_s = min(avg_overlap * (num_bars / 5.0), 1.5)

    # --- 3. 动态动能惩罚 (除法逻辑) ---
    # 如果 CD 段单根实体超过 1.0 ATR，则分数开始快速衰减
    if max_body_ratio > 1.0:
        penalty = max(1.0 / (max_body_ratio ** 2), 0.2)
    else:
        penalty = 1.0

    # --- 4. 撬棍因子 (D点拒绝力度 - lev_s) ---
    if is_bull:
        protrusion = min(d_bar['open'], d_bar['close']) - d_bar['low']
    else:
        protrusion = d_bar['high'] - max(d_bar['open'], d_bar['close'])

    # 影线相对于 ATR 必须有统治力，否则视为无效
    lev_s = min((protrusion / (atr * 0.6 + 1e-10)) * 1.2, 1.5)

    # --- 5. 权重平衡与最终分 ---
    # 顿度(40%) + 碎度(40%) + 撬棍(20%)，最后乘上动态惩罚系数
    q_score = (exp_s * 0.4 + acc_s * 0.4 + lev_s * 0.2) * penalty

    return round(q_score, 2), round(acc_s, 2), round(exp_s, 2), round(lev_s, 2)

# ── TP计算 ───────────────────────────────────────
def calc_harmonic_targets(df, d_bar_idx, is_bull, a_price, sl, x_price, x_idx, a_idx):
    # 1. 调用质量评估
    q_score, acc_s, exp_s, lev_s = evaluate_harmonic_quality(
        df, d_bar_idx, is_bull, a_price, x_price, a_idx, x_idx
    )

    # 3. 目标位计算逻辑
    d_price = df['low'].iloc[d_bar_idx] if is_bull else df['high'].iloc[d_bar_idx]
    ad_range = abs(a_price - d_price)

    # 动态比例：基础 0.5 (陡峭保底)，根据评分加权
    # 如果是积蓄+爆发+尖角突出，比例会向 0.707+ 靠拢
    dynamic_ratio = 0.382 + (q_score * 0.18)
    tp1_ratio = max(0.382, min(dynamic_ratio, 0.786))

    if is_bull:
        tp1 = d_price + ad_range * tp1_ratio
        tp2 = max(d_price + ad_range * 0.886, tp1 + ad_range * 0.146)
        # 针对高质量信号，tp2 设为 X 点 (反转目标)
        if q_score > 0.85: tp2 = x_price
    else:
        tp1 = d_price - ad_range * tp1_ratio
        tp2 = min(d_price - ad_range * 0.886, tp1 - ad_range * 0.146)
        if q_score > 0.85: tp2 = x_price

    # 4. 盈亏比计算 (以 D 点为入场参考，计算基于 SL 的风险)
    entry_ref = d_price
    risk = abs(entry_ref - sl) + 1e-10
    rr1 = abs(tp1 - entry_ref) / risk
    rr2 = abs(tp2 - entry_ref) / risk

    # 5. 严格返回四个参数
    return round(tp1, 2), round(tp2, 2), round(rr1, 2), round(rr2, 2)

# ══════════════════════════════════════════════════════
# ── 主扫描函数 ────────────────────────────────────────
# ══════════════════════════════════════════════════════
def get_local_momentum_direction(df, target_idx):
    """
    在形态转折点（c3，即 target_idx - 2）附近判定局部 K 线动量。
    参数:
        df: 完整的 DataFrame
        target_idx: 形态确认点的索引（通常是 D 点/第二个 B）
    返回: 1 (看涨), -1 (看跌), 0 (无方向)
    """
    # 基础安全检查
    if target_idx < 2 or target_idx >= len(df):
        return 0

    # ── 1. 锚点定位：关键点是 c3 (你图中 17:00 的那根线) ──
    c1 = df.iloc[target_idx]  # 18:00 (确认线)
    c2 = df.iloc[target_idx - 1]  # 17:30 (过渡线)
    c3 = df.iloc[target_idx - 2]  # 17:00 (核心转折线/最低点)

    # ── 2. 基础数值准备 (针对 c3 进行核心判断) ──
    range3 = max(c3.high - c3.low, 1e-5)
    body3_size = abs(c3.close - c3.open)
    body3_top = max(c3.open, c3.close)
    body3_bottom = min(c3.open, c3.close)

    body2_size = abs(c2.close - c2.open)
    body1_size = abs(c1.close - c1.open)

    # ── 3. 判定看涨形态 (Bullish) ──

    # [A] 核心转折点 Pinbar (c3 下影线)
    is_bull_pin = (body3_bottom - c3.low) > (range3 * 0.6)

    # [B] 2B 反包 / 吞没 (c2 或 c1 吞没 c3)
    # 价格在 17:30 或 18:00 强力收复了 17:00 的高点
    is_bull_engulf = (c2.close > c3.high and c2.close > c2.open) or \
                     (c1.close > c3.high and c1.close > c1.open)

    # [C] 启明星 Morning Star
    # c3(阴/星) -> c2(阳确认) -> c1(阳延续)
    # 且 c1 的收盘价切入 c3 实体的一半以上
    is_morning_star = (c3.close < c3.open and
                       body2_size < (c3.high - c3.low) * 0.4 and
                       c1.close > c1.open and
                       c1.close > (c3.open + c3.close) / 2)

    # ── 4. 判定看跌形态 (Bearish) ──
    # 逻辑同理，以 c3 (最高点) 为核心
    range3_bear = max(c3.high - c3.low, 1e-5)
    is_bear_pin = (c3.high - body3_top) > (range3_bear * 0.6)
    is_bear_engulf = (c1.close < c3.low and c1.close < c1.open)

    is_evening_star = (c3.close > c3.open and
                       body2_size < (c3.high - c3.low) * 0.4 and
                       c1.close < c1.open and
                       c1.close < (c3.open + c3.close) / 2)

    # ── 5. 结果综合输出 ──
    if is_bull_pin or is_bull_engulf or is_morning_star:
        return 1

    if is_bear_pin or is_bear_engulf or is_evening_star:
        return -1

    # 保底：如果 c1 动能极强，也给个方向
    if c1.close > c1.open and c1.close > (c2.high + c2.low) / 2:
        return 1
    elif c1.close < c1.open and c1.close < (c2.high + c2.low) / 2:
        return -1

    return 0

def scan_harmonic_smc(df: pd.DataFrame, timeframe: str,
                      require_pivot_confirmation: bool = True) -> dict | None:
    """
    对单个时间周期执行 谐波 + SMC + DB + TD + 入场窗口 全流程扫描。
    """
    if df is None or len(df) < 50: return None

    # --- 基础数据准备 ---
    # df 保留原始数据用于现价/区间展示；
    # zigzag_df 只用于已完成 K 线相关的结构识别。
    if df is None or len(df) < 50:
        return None

    current_price = float(df["close"].iloc[-1])
    zigzag_df = df.iloc[:-1].copy()
    if len(zigzag_df) < 50:
        return None

    atr = float(calc_atr(zigzag_df).iloc[-1])
    zone, zone_pct = get_zone(current_price, df=df)

    # ── 1. ZigZag 计算 ──
    indices, prices, dirs, _ = get_pine_zigzag(
        zigzag_df, length=HARMONIC_ZZ_LENGTH, max_size=HARMONIC_ZZ_SIZE
    )

    # 保守模式：最后一个 pivot 需有 D 点之后一根“已收线 K”做颜色翻转确认。
    # 顺势模式：不需要这根确认K，直接使用最新已完成 D 点。
    last_pivot_confirmed = is_last_pivot_confirmed(zigzag_df, indices, dirs)
    if (not require_pivot_confirmation) or last_pivot_confirmed:
        confirmed_prices = prices
        confirmed_indices = indices
    else:
        confirmed_prices = prices[:-1]
        confirmed_indices = indices[:-1]
    if len(confirmed_prices) < 4:
        return None

    xabcd_result = None
    abcd_result = None
    a_val = 0.0
    x_val = 0.0
    b_val = None
    c_val = None
    x_idx_zz = 0
    a_idx_zz = 0
    b_idx_zz = 0
    c_idx_zz = int(confirmed_indices[-2])

    if len(confirmed_prices) >= 5:
        p5 = confirmed_prices[-5:]
        x_val = float(p5[0])
        a_val = float(p5[1])  # A点
        b_val = float(p5[2])
        c_val = float(p5[3])
        x_idx_zz = int(confirmed_indices[-5])  # X点在df中的索引
        a_idx_zz = int(confirmed_indices[-4])  # A点在df中的索引
        b_idx_zz = int(confirmed_indices[-3])
        c_idx_zz = int(confirmed_indices[-2])

        # ── 2. 核心检测：先判已确认的 XABCD 谐波 ──
        xabcd_result = detect_harmonic(
            confirmed_prices, indices=confirmed_indices, err_pct=HARMONIC_ERROR_PCT
        )

        # ── 过延伸过滤：BD/CD 任一段 > XA×2 则跳过（图三 Crab 类型误报） ──
        if xabcd_result is not None:
            _p = confirmed_prices[-5:]
            _xa = abs(_p[1] - _p[0]) + 1e-10
            _bd = abs(_p[4] - _p[2])
            _cd = abs(_p[4] - _p[3])
            if _bd > _xa * 2.0 or _cd > _xa * 2.0:
                xabcd_result = None

    if xabcd_result is None and len(prices) >= 5:
        if require_pivot_confirmation:
            abcd_prices = prices[:-1]
            abcd_indices = indices[:-1]
        else:
            abcd_prices = prices
            abcd_indices = indices
        p4 = list(abcd_prices[-4:])
        a_val = float(p4[0])
        b_val = float(p4[1])
        c_val = float(p4[2])
        abcd_result = detect_abcd_pattern(
            abcd_prices, indices=abcd_indices, err_pct=HARMONIC_ERROR_PCT
        )

    # db_result = detect_double_pattern(
    #     prices=prices,
    #     dirs=dirs,
    #     bars_indices=indices,
    #     max_risk_per_reward=HARMONIC_DB_MAX_RRP  # 使用配置中的参数
    # )
    # if db_result["type"] is not None:
    #     # 假设你的 detect_double_pattern 返回了 D 点索引，如果没有，默认用最后一根
    #     target_idx = db_result.get("d_bar_idx", len(df) - 1)
    # else:
    target_idx = len(zigzag_df) - 1


    pattern_name = None
    is_bull = False

    # 2. 优先级判定：优先处理双底/双顶（因为你要解决 DB/DT 的过滤问题）
    # if db_result["type"] == "DB":
    #     is_bull = True
    #     pattern_name = "DoubleBottom"
    # elif db_result["type"] == "DT":
    #     is_bull = False
    #     pattern_name = "DoubleTop"

    # 3. 如果没双底双顶，再看有没有谐波
    if xabcd_result is not None:
        pattern_name, is_bull = xabcd_result
    elif abcd_result is not None:
        pattern_name, is_bull = abcd_result

    # 4. 判定 has_double 状态（保持你后续逻辑需要的变量名）
    # has_db = (db_result["type"] == "DB" and is_bull)
    # has_dt = (db_result["type"] == "DT" and not is_bull)
    # has_double = has_db or has_dt

    # 5. 最终准入：必须有形态
    if pattern_name is None: #(and not has_double)
        return None

    # 6. 保底方向逻辑（用于没有任何形态但需要方向时，或给后续逻辑参考）
    # 只有在没有确定形态时，才根据 momentum_dir 给 is_bull 赋值
    if pattern_name is None:
        momentum_dir = get_local_momentum_direction(zigzag_df, target_idx)
        is_bull = (momentum_dir == 1)

    # ── 3. 基础过滤（溢价区/D点距离） ──
    # is_pure_double = "Double" in str(pattern_name)
    # if not is_pure_double:
    #     if is_bull and zone == "premium": return None
    #     if not is_bull and zone == "discount": return None

    d_price = float(confirmed_prices[-1])
    d_bar_idx = int(confirmed_indices[-1])
    pattern_family = "ABCD-family" if pattern_name in {"ABCD", "AB=CD", "ABCD Ext"} else "XABCD-family"
    latest_closed_idx = len(zigzag_df) - 1

    # XABCD 下单时机收紧：
    # 1. 有父级顺势时，不等确认，D 必须是最新一根已完成K；
    # 2. 无父级时，最多只允许 D 后一根确认K，不能拖到更后面。
    if pattern_family == "XABCD-family":
        if require_pivot_confirmation:
            if (not last_pivot_confirmed) or d_bar_idx != latest_closed_idx - 1:
                return None
        else:
            if d_bar_idx != latest_closed_idx:
                return None

    if abs(current_price - d_price) > atr * 3:
        log_scan_skip(
            f"  [过滤-{timeframe}] {pattern_name} "
            f"当前价距D={abs(current_price - d_price):.2f} > ATR×3={atr * 3:.2f} "
            f"price={current_price:.2f} D={d_price:.2f}"
        )
        return None

    # ── 4. 入场窗口过滤 ──
    # is_pure_double = pattern_name in ["DoubleBottom", "DoubleTop"]
    #
    # if is_pure_double:
    #     # 1. 获取 D 点 K 线（最新枢纽点）的高低点
    #     # d_bar_idx 是 ZigZag 确定的 D 点索引
    #     d_high = float(df["high"].iloc[d_bar_idx])
    #     d_low = float(df["low"].iloc[d_bar_idx])
    #
    #     # 2. 计算 50% 的位置作为 Entry
    #     entry_at_50 = (d_high + d_low) / 2
    #
    #     # 3. 强制覆盖 entry_win 逻辑：不检查回踩，直接设为 D 点 K 线的一半位置触发
    #     entry_win = {
    #         "triggered": True,
    #         "entry_price": round(entry_at_50, 2),
    #         "trigger_bar": d_bar_idx,
    #         "d_range": round(d_high - d_low, 2)
    #     }
    # else:
    # 如果是普通谐波形态（Bat, Butterfly 等），保留你原来的回踩入场逻辑
    # 提取C点价格（confirmed_prices[-5:] = [X,A,B,C,D]，C = [-2]）
    c_price_for_entry = float(confirmed_prices[-2]) if len(confirmed_prices) >= 4 else None
    cd_price_len = abs(c_price_for_entry - d_price) if c_price_for_entry is not None else 0.0
    entry_win = check_entry_window(zigzag_df, d_bar_idx, is_bull,
                                   entry_bars=HARMONIC_ENTRY_BARS + 1,
                                   c_price=c_price_for_entry)

    # 统一检查是否准入
    if not entry_win["triggered"]:
        log_scan_skip(f"  [过滤-{timeframe}] {pattern_name} 入场窗口未触发")
        return None

    entry_price = entry_win["entry_price"]

    # D→C 0.786 是计划入场价，不再作为谐波信号准入过滤。
    # 旧逻辑用 0.236 时这个距离过滤还能成立；改成 0.786 后会误杀 30m/1h 信号。

    # ── 5. SMC 确认项与评分 ──
    has_sweep = check_sweep_at_d(zigzag_df, d_price, is_bull, atr, n=HARMONIC_SWEEP_BARS)
    obs = find_obs_near_d(zigzag_df, d_price, atr)
    ob_match = [o for o in obs if o["type"] == ("bullish" if is_bull else "bearish")]
    has_fvg = check_fvg_after_d(zigzag_df, d_bar_idx, is_bull)
    has_choch = check_choch_at_d(zigzag_df, d_bar_idx, is_bull, lookback=8)

    vol_confirmed = False
    if "volume" in zigzag_df.columns and d_bar_idx < len(zigzag_df):
        recent_vol = zigzag_df["volume"].iloc[-HARMONIC_SWEEP_BARS:].mean()
        avg_vol_ref = zigzag_df["volume"].iloc[-30:-HARMONIC_SWEEP_BARS].mean() + 1e-10
        vol_confirmed = bool(recent_vol > avg_vol_ref * 1.1)

    # ── 6. TD 计数与 PRZ 评分 ──
    prz_score, prz_detail = score_prz_quality(confirmed_prices, pattern_name, HARMONIC_ERROR_PCT)

    td_result = {"found": False, "td_values": []}
    has_td_in_db = False
    # if has_double:
    #     offset1 = db_result.get("bottom1_zz_offset", db_result.get("top1_zz_offset", -3))
    #     offset2 = db_result.get("bottom2_zz_offset", db_result.get("top2_zz_offset", -1))
    #     n_pts = len(indices)
    #     idx1 = indices[n_pts + offset1] if n_pts + offset1 >= 0 else 0
    #     idx2 = indices[n_pts + offset2] if n_pts + offset2 >= 0 else 0
    #     td_result = check_td_between_bottoms(df, min(idx1, idx2), max(idx1, idx2))
    #     has_td_in_db = td_result["found"]

    # 综合 SMC 评分
    smc_score = (int(has_sweep) + int(len(ob_match) > 0) + int(has_fvg)
                 + int(has_choch) + int(vol_confirmed))
    # if has_double:   smc_score += 1
    # if has_td_in_db: smc_score += 1

    #初期不需要 放开所有限制
    # if smc_score < (1 if has_choch else 2): return None

    # ── 7. 谐波 TP 与反推 SL ───────────────────────────────────────
    # 所有 TP 统一按 C -> D 轴计算：
    # - D = 0
    # - C = 1
    tp1 = d_price + (c_price_for_entry - d_price) * HARMONIC_TP1_CD_RATIO
    tp2 = d_price + (c_price_for_entry - d_price) * HARMONIC_TP2_CD_RATIO

    stop_rr = max(HARMONIC_STOP_RR, 0.1)
    risk_amt = abs(tp1 - entry_price) / stop_rr
    sl_by_rr = entry_price - risk_amt if is_bull else entry_price + risk_amt

    d_low = float(entry_win.get("d_low", zigzag_df["low"].iloc[d_bar_idx]))
    d_high = float(entry_win.get("d_high", zigzag_df["high"].iloc[d_bar_idx]))
    sl_by_d = d_low * (1.0 - HARMONIC_SL_BUFFER) if is_bull else d_high * (1.0 + HARMONIC_SL_BUFFER)

    tp1_half_risk = abs(tp1 - entry_price) * max(HARMONIC_TP1_STOP_FRAC, 0.01)
    sl_by_tp1_half = entry_price - tp1_half_risk if is_bull else entry_price + tp1_half_risk

    # 取更紧的止损：
    # 多单止损越高越紧，空单止损越低越紧
    if is_bull:
        sl = max(sl_by_d, sl_by_tp1_half)
    else:
        sl = min(sl_by_d, sl_by_tp1_half)

    # 盈亏比
    risk_amt = abs(entry_price - sl) + 1e-10
    rr1 = round(abs(tp1 - entry_price) / risk_amt, 2)
    rr2 = round(abs(tp2 - entry_price) / risk_amt, 2)

    # 最低 RR 门槛（RR=2 下保底，避免因 D点K线极大导致失效）
    if rr1 < HARMONIC_MIN_RR:
        log_scan_skip(
            f"  [过滤-{timeframe}] {pattern_name} rr1={rr1} < HARMONIC_MIN_RR={HARMONIC_MIN_RR}"
        )
        return None

    # ── 8. 构建最终结果 ──
    conf_parts = []
    if has_sweep:    conf_parts.append("Sweep✓")
    if ob_match:     conf_parts.append(f"OB✓({len(ob_match)})")
    if has_fvg:      conf_parts.append("FVG✓")
    if has_choch:    conf_parts.append("CHoCH✓")
    if vol_confirmed: conf_parts.append("Vol✓")
    # if has_db:       conf_parts.append("DB✓")
    # if has_dt:       conf_parts.append("DT✓")
    if has_td_in_db: conf_parts.append(f"TD✓")

    grade_label = "A★★★" if smc_score >= 5 else ("B★★" if smc_score >= 3 else "C★")

    return {
        "timeframe": timeframe, "direction": "LONG" if is_bull else "SHORT",
        "pattern": pattern_name, "grade": f"Harmonic-{pattern_name}-{grade_label}",
        "pattern_family": pattern_family,
        "entry": float(entry_price), "d_price": float(d_price), "stop_loss": float(sl),
        "target1": tp1, "target2": tp2, "rr1": rr1, "rr2": rr2,
        "zone": zone, "zone_pct": zone_pct, "smc_score": smc_score,
        "prz_score": prz_score, "prz_detail": " | ".join(prz_detail),
        "has_sweep": has_sweep, "has_ob": len(ob_match) > 0, "has_fvg": has_fvg,
        "has_choch": has_choch, "vol_ok": vol_confirmed,
        # "has_db": has_db, "has_dt": has_dt, "db_rrp": db_result.get("rrp", 0.0), "has_td_in_db": has_td_in_db,
        # "td_values": td_result.get("td_values", []),
        "confidence": f"SMC {smc_score}/7  PRZ {prz_score}/4 | {' '.join(conf_parts)}",
        "conf_parts": conf_parts, "atr": float(atr), "price": float(current_price),
        "entry_d_range": entry_win["d_range"], "trigger_bar": entry_win["trigger_bar"],
        "x_price": float(x_val) if x_val else None,
        "a_price": float(a_val) if a_val else None,
        "b_price": float(b_val) if b_val is not None else None,
        "x_bar_idx": int(x_idx_zz) if pattern_family == "XABCD-family" else None,
        "a_bar_idx": int(a_idx_zz) if pattern_family == "XABCD-family" else None,
        "b_bar_idx": int(b_idx_zz) if pattern_family == "XABCD-family" else None,
        "c_bar_idx": int(c_idx_zz) if pattern_family == "XABCD-family" else None,
        "x_bar_time": str(zigzag_df["timestamp"].iloc[x_idx_zz]) if pattern_family == "XABCD-family" else None,
        "a_bar_time": str(zigzag_df["timestamp"].iloc[a_idx_zz]) if pattern_family == "XABCD-family" else None,
        "b_bar_time": str(zigzag_df["timestamp"].iloc[b_idx_zz]) if pattern_family == "XABCD-family" else None,
        "c_bar_time": str(zigzag_df["timestamp"].iloc[c_idx_zz]) if pattern_family == "XABCD-family" else None,
        "cd_len": entry_win.get("cd_len", 0),
        "c_price": float(c_val if c_val is not None else c_price_for_entry)
                   if (c_val is not None or c_price_for_entry is not None) else None,
        "cd_price_len": float(cd_price_len),
        "d_bar_time": str(zigzag_df["timestamp"].iloc[d_bar_idx]),
        "pivot_confirmed": last_pivot_confirmed,
        "require_pivot_confirmation": require_pivot_confirmation,
        "raw_last5": [round(float(v), 8) for v in prices[-5:]],
        "confirmed_last5": [round(float(v), 8) for v in confirmed_prices[-5:]],
        "used_raw_latest_pivot": not require_pivot_confirmation,
        "tp_anchor": "C→D",
        "tp_ratio": HARMONIC_TP1_CD_RATIO,
        "tp2_anchor": "C→D",
        "tp2_ratio": HARMONIC_TP2_CD_RATIO,
    }

# ── 格式化输出 ────────────────────────────────────
def format_signal(sig: dict) -> str:
    """
    格式化输出信号，包含：
    1. 时间周期与价格概况
    2. SMC 五项确认指标
    3. 谐波形态具体斐波那契比例 (PRZ Detail)
    4. 修正后的入场、止损、止盈及真实 RR
    """
    d = sig["direction"]
    dc = GREEN if d == "LONG" else RED
    direction_label = "LONG" if d == "LONG" else "SHORT"
    tp1_anchor = sig.get("tp_anchor", "CD")
    tp1_ratio = sig.get("tp_ratio", HARMONIC_TP1_CD_RATIO)
    tp2_anchor = sig.get("tp2_anchor", "CD")
    tp2_ratio = sig.get("tp2_ratio", HARMONIC_TP2_CD_RATIO)
    if sig.get("require_pivot_confirmation", True):
        confirm_mode = "已确认D点"
    else:
        confirm_mode = "父级顺势提前D点"
    if sig.get("used_raw_latest_pivot"):
        confirm_mode += " raw=confirmed"
    order_status = sig.get("order_status", "未判定")
    order_status_reason = sig.get("order_status_reason", "")
    price_decimals = int(sig.get("price_decimals", 2))

    def pf(v) -> str:
        return f"{float(v):,.{price_decimals}f}"

    if sig.get("use_market_entry"):
        planned_entry = sig.get("planned_entry")
        entry_mode_text = "市价入场"
        if planned_entry is not None:
            entry_mode_text += f" 理论D→C0.786={pf(planned_entry)}"
    else:
        entry_mode_text = "D→C×0.786入场"

    # ── DB/DT 与 TD 的辅助显示 ──
    db_str = ""
    if sig.get("has_db") or sig.get("has_dt"):
        pat = "DB" if sig.get("has_db") else "DT"
        db_str = f"  {DIM}{pat}(rrp={sig['db_rrp']}%)"
        if sig.get("has_td_in_db"):
            td_nums = [str(abs(v)) for v in sig.get("td_values", [])[:3]]
            db_str += f"  TD({','.join(td_nums)})✓"
        db_str += RESET

    # ── 核心内容构建 ──
    title_prefix = "sos " if sig.get("timeframe") in {"4h", "1d"} else ""

    lines = [
        f"\n{BOLD}── {sig['timeframe']} ─────────────────────────────────{RESET}",
        f"  Price   : {BOLD}${pf(sig['price']):>12}{RESET}  ATR={sig['atr']:.1f}",
        f"  Zone    : {sig['zone']} {sig['zone_pct']}%",
        f"\n  {BOLD}{dc}╔══ Signal Trigger ══ {title_prefix}{direction_label} {sig['pattern']:<8} ══ {sig['grade']} ═╗{RESET}",
        f"  {DIM}Pattern : {sig.get('pattern_family', 'XABCD-family')}{RESET}",

        # 1. SMC 逐项确认情况
        (f"  {DIM}SMC {sig['smc_score']}/7  "
         f"Sweep={'✓' if sig['has_sweep'] else '✗'}  "
         f"OB={'✓' if sig['has_ob'] else '✗'}  "
         f"FVG={'✓' if sig['has_fvg'] else '✗'}  "
         f"CHoCH={'✓' if sig.get('has_choch') else '✗'}  "
         f"Vol={'✓' if sig.get('vol_ok') else '✗'}  "
         f"DB/DT={'✓' if (sig.get('has_db') or sig.get('has_dt')) else '✗'}  "
         f"TD={'✓' if sig.get('has_td_in_db') else '✗'}{RESET}"),

        # 2. 谐波比例详情 (XAB, ABC, XAD 等)
        f"  {YELLOW}PRZ质量 {sig.get('prz_score', 0)}/4  {sig.get('prz_detail', '')}{RESET}",
    ]

    # 3. 打印 Conf 因素列表
    if sig.get("conf_parts"):
        lines.append(f"  {DIM}Conf因素: {' | '.join(sig['conf_parts'])}{RESET}")
    if db_str:
        lines.append(db_str)

    # 4. 交易数据：Entry, Stop, TP
    # 注意：入场描述改为 "回踩入场"，分腿 TP 描述修正为 CDx0.49
    has_staged_legs = (
        sig.get("leg_a_entry") is not None and
        sig.get("leg_b_entry") is not None and
        sig.get("leg_c_entry") is not None and
        sig.get("leg_d_entry") is not None
    )
    hide_entry_line = bool(sig.get("hide_entry_line"))
    hide_tp2_line = bool(sig.get("hide_tp2_line"))

    trade_lines = [f"  {'─' * 56}"]
    if sig.get("execution_mode_desc"):
        trade_lines.append(f"  Mode    : {sig['execution_mode_desc']}")
    if not hide_entry_line:
        if has_staged_legs:
            trade_lines.append(
                f"  Ref-CD1.12 : {BOLD}${pf(sig.get('tier1_entry', sig['entry'])):>10}{RESET}  "
                f"(D点={pf(sig['d_price'])}  C→D 1.12参考位  cd={pf(sig.get('cd_price_len',0))})"
            )
        else:
            trade_lines.append(
                f"  Entry   : {BOLD}${pf(sig['entry']):>12}{RESET}  "
                f"(D点={pf(sig['d_price'])}  "
                f"{entry_mode_text}  "
                f"cd={pf(sig.get('cd_price_len',0))})"
            )
    if sig.get("entry_plan_text"):
        if sig.get("sniper_legs"):
            trade_lines.append("  Legs    :")
            for leg in sig["sniper_legs"]:
                trade_lines.append(
                    f"    {leg.get('name', 'Sniper')}: "
                    f"Entry={pf(leg.get('entry'))} TP={pf(leg.get('target'))} "
                    f"数量={leg.get('size', '?')} RR={leg.get('rr', '?')}R"
                )
        else:
            trade_lines.append(f"  Legs    : {sig['entry_plan_text']}")
    trade_lines.append(
        "  XABCD   : "
        f"X={pf(sig.get('x_price')) if sig.get('x_price') is not None else 'n/a'}  "
        f"A={pf(sig.get('a_price')) if sig.get('a_price') is not None else 'n/a'}  "
        f"B={pf(sig.get('b_price')) if sig.get('b_price') is not None else 'n/a'}  "
        f"C={pf(sig.get('c_price')) if sig.get('c_price') is not None else 'n/a'}  "
        f"D={pf(sig.get('d_price')) if sig.get('d_price') is not None else 'n/a'}"
    )
    if sig.get("tier1_entry") is not None:
        trade_lines.append(
            f"  Risk    : CD×1.13={pf(sig['tier1_entry'])}  AvgEntry={pf(sig['avg_entry'])}  "
            f"HardStop={pf(sig['hard_stop'])}  Equity={pf(sig['risk_equity'])}  Qty={pf(sig['risk_total_size'])}"
        )
    trade_lines += [
        f"  D-Info  : {sig.get('d_bar_time', 'n/a')}  {confirm_mode}  触发Bar={sig.get('trigger_bar', -1)}",
        f"  D-Range : {pf(sig.get('entry_d_range', 0))}",
    ]
    if has_staged_legs:
        trade_lines += [
            f"  Leg-A   : Entry={pf(sig['leg_a_entry'])}  Stop={pf(sig['leg_a_stop'])}  "
            f"TP={pf(sig['leg_a_tp1'])}  Size={sig.get('leg_a_size','?')}  "
            f"(RR≈{sig['leg_a_rr1']}R  {sig.get('leg_a_entry_label', 'CD×1.12')} / {sig.get('leg_a_tp_label', 'TP=C→D×0.786')})",
            f"  Leg-B   : Entry={pf(sig['leg_b_entry'])}  Stop={pf(sig['leg_b_stop'])}  "
            f"TP={pf(sig['leg_b_tp1'])}  Size={sig.get('leg_b_size','?')}  "
            f"(RR≈{sig['leg_b_rr1']}R  {sig.get('leg_b_entry_label', 'CD×1.272')} / {sig.get('leg_b_tp_label', 'TP=C→D×0.786')})",
            f"  Leg-C   : Entry={pf(sig['leg_c_entry'])}  Stop={pf(sig['leg_c_stop'])}  "
            f"TP={pf(sig['leg_c_tp1'])}  Size={sig.get('leg_c_size','?')}  "
            f"(RR≈{sig['leg_c_rr1']}R  {sig.get('leg_c_entry_label', 'CD×1.414')} / {sig.get('leg_c_tp_label', 'TP=C→D×0.786')})",
            f"  Leg-D   : Entry={pf(sig['leg_d_entry'])}  Stop={pf(sig['leg_d_stop'])}  "
            f"TP={pf(sig['leg_d_tp1'])}  Size={sig.get('leg_d_size','?')}  "
            f"(RR≈{sig['leg_d_rr1']}R  {sig.get('leg_d_entry_label', 'CD×1.618')} / {sig.get('leg_d_tp_label', 'TP=C→D×0.786')})",
        ]
    else:
        stop_line = (
            f"  Stop    : {RED}${pf(sig['hard_stop']):>12}{RESET}  (统一硬止损 CD×1.734+8tick)"
            if sig.get("hard_stop") is not None and hide_entry_line else
            f"  Stop    : {RED}${pf(sig['stop_loss']):>12}{RESET}"
        )
        trade_lines.append(stop_line)
        if sig.get("trailing_exit"):
            signal_tf = sig.get("sniper_signal_tf") or sig.get("timeframe", "?")
            final_tf = sig.get("sniper_trail_tf", "15m")
            start_bars = sig.get("sniper_trail_start_bars", 3)
            final_ratio = sig.get("sniper_final_tp_ratio", 2.618)
            trade_lines.append(
                f"  Exit    : {GREEN}Sniper移动止盈止损{RESET}  "
                f"({start_bars}根{signal_tf}后按{signal_tf}实体推进，"
                f"{final_tf}检查C→D×{final_ratio}市价平仓，参考RR≈{sig['rr1']}R)"
            )
        else:
            trade_lines.append(
                f"  TP1     : {GREEN}${pf(sig['target1']):>12}{RESET}  (RR≈{sig['rr1']}R  {tp1_anchor}×{tp1_ratio})"
            )

    lines += [
        *trade_lines,
        f"  Status  : {order_status}" + (f"  ({order_status_reason})" if order_status_reason else ""),
        f"  Conf    : {MAGENTA}{sig['confidence']}{RESET}",
        f"  {BOLD}{dc}╚{'═' * 54}╝{RESET}",
    ]

    return "\n".join(lines)


# ── 主循环（独立运行时使用）─────────────────────────
def main():
    print(f"{BOLD}{CYAN}Harmonic+SMC Scanner v2 | {SYMBOL}{RESET}")
    exchange = ccxt.bitget({"enableRateLimit": True, "timeout": 15000})
    exchange.load_markets()

    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{CYAN}{'═'*60}{RESET}\n{BOLD}  {now}{RESET}")
        found_any = False

        for tf in TIMEFRAMES:
            limit = TF_FETCH_LIMIT.get(tf, 300)
            df    = fetch_ohlcv(exchange, SYMBOL, tf, limit=limit)
            sig   = scan_harmonic_smc(df, tf)
            if sig:
                print(format_signal(sig))
                found_any = True
            else:
                p = float(df["close"].iloc[-1]) if df is not None else 0
                print(f"{DIM}  [{tf}] ${p:,.0f} — no harmonic signal{RESET}")

        if not found_any:
            print(f"{DIM}  No signals this round.{RESET}")

        try:
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
