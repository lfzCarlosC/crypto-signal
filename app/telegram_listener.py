"""
独立的 Telegram 查询监听脚本：长轮询 Telegram getUpdates，接收形如 "/btcusdt" 的
命令，查询 signals.sqlite3 里这个币种最近的信号（按时间倒序，默认5条），回复
信号名称、信号所在的交易级别(candle_period)、以及信号产生的时间。

跟 behaviour.py 是完全独立的进程：
  - behaviour.py 每次扫描命中一条"新"信号（toDb() 判定为新信号，真正发出了
    Telegram 通知）时，会把这条信号顺带写进 signals.sqlite3（见
    Behaviour._record_signal_sqlite()）。
  - 这个脚本只对 signals.sqlite3 做只读查询，不写入，可以单独常驻运行
    （比如用 supervisor/systemd 常驻，或者 screen/tmux 里跑），
    不需要跟着 behaviour.py 的定时调度一起启动/停止。

两边必须共用同一个 signals.sqlite3 文件——默认都是脚本所在目录下的
"signals.sqlite3"，只要两个脚本部署在同一个目录下就会自动一致，不需要额外配置。

用法：
    python telegram_query_listener.py

依赖：只用到 requests + 标准库，不需要额外安装 python-telegram-bot 之类的库。
"""

import os
import sqlite3
import time

import ccxt
import requests

from notification import Notifier

BOT_TOKEN = Notifier.tg_bot_token
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../signals.sqlite3")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 30  # Telegram长轮询超时(秒)，getUpdates会在这段时间内一直挂起等新消息
RESULT_LIMIT = 5   # 每次查询返回的最大信号条数

# ── /1w1m 命令用：实时拉取OHLCV算RSI，不走 signals.sqlite3 那套 ────────────
# 用哪个交易所拉行情。这个脚本本身跟 behaviour.py 用的 ExchangeInterface
# 是完全独立的两套东西（behaviour.py那边配置在它自己的config里，这里没有复用），
# 默认用 Binance 公开行情接口（不需要API Key）。如果你们主要交易所不是Binance，
# 改这一个常量即可，比如 "okx"/"bybit" 等 ccxt 支持的交易所id。
CCXT_EXCHANGE_ID = "binance"

RSI_ENTRY_THRESHOLD = 30.9   # "超卖进入"阈值，向上突破视为breakout
RSI_RECOVER_THRESHOLD = 69.0  # "超买回落"阈值，向下跌破视为recover

_ccxt_exchange = None  # 懒加载单例

# 1. 确保使用绝对路径定位 sqlite 文件
SQLITE_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "signals.sqlite3")
)


def get_ccxt_exchange():
    """懒加载一个只读的 ccxt 交易所实例，只用于 /1w1m 命令实时拉OHLCV算RSI，
    不需要API Key（公开行情接口），全局单例避免每次查询都重新创建。"""
    global _ccxt_exchange
    if _ccxt_exchange is None:
        exchange_cls = getattr(ccxt, CCXT_EXCHANGE_ID)
        _ccxt_exchange = exchange_cls({"enableRateLimit": True})
    return _ccxt_exchange


def normalize_to_ccxt_symbol(raw_symbol: str) -> str | None:
    """把 "btcusdt"/"BTC-USDT"/"btc/usdt" 这类用户输入统一转成 ccxt 的
    unified symbol 格式 "BTC/USDT"。识别不出计价货币（比如输入的不是常见的
    USDT/USDC/BUSD/USD/BTC/ETH 结尾）时返回 None。"""
    s = raw_symbol.strip().upper().replace("/", "").replace("-", "")
    for quote in ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}/{quote}"
    return None


def fetch_closed_closes(exchange, symbol: str, timeframe: str, limit: int = 300) -> list[float]:
    """拉取指定 symbol+timeframe 的收盘价数组，只保留【已经收线】的K线。
    ccxt 返回的最后一根K线通常是"当前正在进行中、价格还会变"的那一根，这里统一
    剔除，避免RSI计算/跳变判断被一根还没走完的K线污染。"""
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not raw or len(raw) < 2:
        return []
    raw = raw[:-1]
    return [float(c[4]) for c in raw]


def calc_rsi(closes: list[float], period: int) -> list[float | None]:
    """标准 Wilder's RSI，返回跟 closes 等长的列表；前 period 个位置数据不足，填 None。"""
    n = len(closes)
    rsi: list[float | None] = [None] * n
    if n <= period:
        return rsi

    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        change = closes[i] - closes[i - 1]
        gains[i] = change if change > 0 else 0.0
        losses[i] = -change if change < 0 else 0.0

    avg_gain = sum(gains[1:period + 1]) / period
    avg_loss = sum(losses[1:period + 1]) / period
    rsi[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    return rsi


def find_most_recent_cross(rsi_series: list[float | None]) -> str | None:
    """从最新一根往回扫描（含"跌入当前这一根"这次跳变本身），找最近一次发生的是：
      'breakout' -> RSI 从 <RSI_ENTRY_THRESHOLD(30.9) 涨到 >=30.9（向上穿越进场阈值）
      'recover'  -> RSI 从 >RSI_RECOVER_THRESHOLD(69) 跌到 <=69（向下穿越出场阈值）
    两种都没发生过（历史数据不够长、或者从来没触发过任一阈值）时返回 None。
    """
    for i in range(len(rsi_series) - 1, 0, -1):
        prev, curr = rsi_series[i - 1], rsi_series[i]
        if prev is None or curr is None:
            continue
        if prev < RSI_ENTRY_THRESHOLD <= curr:
            return "breakout"
        if prev > RSI_RECOVER_THRESHOLD >= curr:
            return "recover"
    return None


def evaluate_1w_signal(rsi14_series: list[float | None]) -> bool | None:
    """1w级别判定规则（用RSI14）：
      当前RSI14 <= 30.9  -> False
      当前RSI14 >  30.9  -> 往回找最近一次是breakout还是recover：
                              breakout更近 -> True
                              recover更近  -> False
                              都没发生过    -> None（数据不足，无法判断）
    """
    if not rsi14_series or rsi14_series[-1] is None:
        return None
    current = rsi14_series[-1]
    if current <= RSI_ENTRY_THRESHOLD:
        return False
    direction = find_most_recent_cross(rsi14_series)
    if direction == "breakout":
        return True
    if direction == "recover":
        return False
    return None


def evaluate_1m_signal(rsi7_series: list[float | None]) -> bool | None:
    """1M(月)级别判定规则（用RSI7），注意"当前<=30.9"这一支的结果跟1w相反：
      当前RSI7 <= 30.9  -> True
      当前RSI7 >  30.9  -> 往回找最近一次是breakout还是recover：
                              breakout更近 -> True
                              recover更近  -> False
                              都没发生过    -> None（数据不足，无法判断）
    """
    if not rsi7_series or rsi7_series[-1] is None:
        return None
    current = rsi7_series[-1]
    if current <= RSI_ENTRY_THRESHOLD:
        return True
    direction = find_most_recent_cross(rsi7_series)
    if direction == "breakout":
        return True
    if direction == "recover":
        return False
    return None


def format_bool_result(val: bool | None) -> str:
    if val is None:
        return "无法判断（历史数据不足）"
    return "true" if val else "false"


def handle_1w1m_command(chat_id, symbol_raw: str) -> None:
    """处理 /1w1m <币种> 命令：实时拉取该币种 1w/1M K线，分别用RSI14/RSI7
    判定 evaluate_1w_signal()/evaluate_1m_signal() 的结果并回复。"""
    ccxt_symbol = normalize_to_ccxt_symbol(symbol_raw)
    if not ccxt_symbol:
        send_message(chat_id, f"⚠️ 无法识别币种：{symbol_raw}")
        return

    try:
        exchange = get_ccxt_exchange()
        closes_1w = fetch_closed_closes(exchange, ccxt_symbol, "1w", limit=300)
        closes_1m = fetch_closed_closes(exchange, ccxt_symbol, "1M", limit=300)
    except Exception as e:
        send_message(chat_id, f"⚠️ 拉取 {ccxt_symbol} 行情失败: {e}")
        return

    rsi14_1w = calc_rsi(closes_1w, 14)
    rsi7_1m = calc_rsi(closes_1m, 7)

    result_1w = evaluate_1w_signal(rsi14_1w)
    result_1m = evaluate_1m_signal(rsi7_1m)

    cur_rsi14 = rsi14_1w[-1] if rsi14_1w else None
    cur_rsi7 = rsi7_1m[-1] if rsi7_1m else None
    rsi14_text = f"{cur_rsi14:.1f}" if cur_rsi14 is not None else "n/a"
    rsi7_text = f"{cur_rsi7:.1f}" if cur_rsi7 is not None else "n/a"

    lines = [
        f"🔎 {ccxt_symbol} 1w / 1M 信号判定：",
        f"  1w (RSI14={rsi14_text}): {format_bool_result(result_1w)}",
        f"  1M (RSI7={rsi7_text}): {format_bool_result(result_1m)}",
    ]
    send_message(chat_id, "\n".join(lines))


def query_signals(symbol: str, limit: int = RESULT_LIMIT) -> list[dict]:
    # 2. 如果文件根本不存在（说明路径指错了），直接返回空，绝不自动新建空库
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"[ERROR] 找不到 SQLite 数据库文件: {SQLITE_DB_PATH}")
        return []

    # 3. 提取纯字母数字做标准化 (btcusdt -> BTCUSDT)
    symbol_norm = "".join(e for e in symbol if e.isalnum()).upper()
    if not symbol_norm:
        return []

    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT market_pair, signal_type, candle_period, created_at FROM signals "
            "ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    matched = []
    seen_keys = set()  # (signal_type, 日期) 去重用；rows已经按created_at DESC排好，
                        # 同一天同一条信号只会保留最新（第一次遇到）的那一条。
    for market_pair, signal_type, candle_period, created_at in rows:
        if not market_pair:
            continue

        # 4. 数据库出来的字段也只留字母数字 (BTC/USDT -> BTCUSDT)
        pair_norm = "".join(e for e in str(market_pair) if e.isalnum()).upper()

        if symbol_norm in pair_norm or pair_norm in symbol_norm:
            # ── 去重：按 (信号内容, 日期) 去重，日期只精确到"天"，不看具体时分秒 ──
            # 同一天同一个 signal_type 反复命中（比如RSI超卖区间连续好几根K线都在
            # 命中）只算一条，避免 /btcusdt 10 里全是同一个信号堆出来的重复条目。
            day_part = str(created_at)[:10]  # created_at是ISO格式字符串，前10位就是"YYYY-MM-DD"
            dedup_key = (signal_type, day_part)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            matched.append({
                "market_pair": market_pair,
                "signal_type": signal_type,
                "candle_period": candle_period,
                "created_at": created_at,
            })
            if len(matched) >= limit:
                break
    return matched

def format_reply(symbol: str, results: list[dict]) -> str:
    """把查询结果拼成给用户看的文本消息。"""
    if not results:
        return f"未找到 {symbol.upper()} 对应的信号记录"

    lines = [f"🔎 {symbol.upper()} 最近 {len(results)} 条信号（按时间从新到旧）："]
    for r in results:
        lines.append(
            f"  [{r['candle_period']}] {r['signal_type']}  {r['created_at']}"
        )
    return "\n".join(lines)


def send_message(chat_id, text: str) -> None:
    try:
        requests.post(
            f"{API_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print(f"[telegram_query_listener] 发送回复失败: {e}")


def handle_update(update: dict) -> None:
    message = update.get("message") or update.get("channel_post")
    if not message:
        return

    text = str(message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not text.startswith("/") or chat_id is None:
        return

    # 1. 拆分参数
    parts = text.split()
    cmd_part = parts[0][1:].split("@", 1)[0].strip()

    if cmd_part.lower() in ("start", "help", ""):
        send_message(
            chat_id,
            "输入 /币种 [条数] 查询信号，例如：\n/btcusdt\n/btcusdt 10\n"
            "输入 /1w1m 币种 查询1w/1M级别RSI信号判定，例如：\n/1w1m btcusdt",
        )
        return

    if cmd_part.lower() == "1w1m":
        if len(parts) < 2 or not parts[1].strip():
            send_message(chat_id, "用法：/1w1m <币种>\n例如：/1w1m btcusdt")
            return
        handle_1w1m_command(chat_id, parts[1].strip())
        return

    # 2. 解析限制条数（默认 5 条）
    limit = RESULT_LIMIT
    if len(parts) > 1:
        try:
            parsed_limit = int(parts[1])
            if parsed_limit > 0:
                limit = parsed_limit
        except ValueError:
            pass

    # 3. 传入 limit 参数查询
    results = query_signals(cmd_part, limit=limit)
    send_message(chat_id, format_reply(cmd_part, results))

def main() -> None:
    print("[telegram_query_listener] 启动，开始长轮询 Telegram 消息 ...")
    print(f"[telegram_query_listener] sqlite库路径: {SQLITE_DB_PATH}")
    offset = None
    while True:
        try:
            params = {"timeout": POLL_TIMEOUT}
            if offset is not None:
                params["offset"] = offset
            resp = requests.get(
                f"{API_BASE}/getUpdates", params=params, timeout=POLL_TIMEOUT + 10
            )
            data = resp.json()
            if not data.get("ok"):
                print(f"[telegram_query_listener] getUpdates失败: {data}")
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle_update(update)
                except Exception as e:
                    print(f"[telegram_query_listener] 处理消息异常: {e}")
        except Exception as e:
            print(f"[telegram_query_listener] 轮询异常: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()