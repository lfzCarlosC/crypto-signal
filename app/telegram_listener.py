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

import requests

from notification import Notifier

BOT_TOKEN = Notifier.tg_bot_token
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../signals.sqlite3")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 30  # Telegram长轮询超时(秒)，getUpdates会在这段时间内一直挂起等新消息
RESULT_LIMIT = 5   # 每次查询返回的最大信号条数

# 1. 确保使用绝对路径定位 sqlite 文件
SQLITE_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "signals.sqlite3")
)


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
    for market_pair, signal_type, candle_period, created_at in rows:
        if not market_pair:
            continue

        # 4. 数据库出来的字段也只留字母数字 (BTC/USDT -> BTCUSDT)
        pair_norm = "".join(e for e in str(market_pair) if e.isalnum()).upper()

        if symbol_norm in pair_norm or pair_norm in symbol_norm:
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
    """处理一条 Telegram getUpdates 返回的消息。只识别形如 "/币种"（比如
    "/btcusdt"、"/BTCUSDT@某bot"）这类命令，其它消息一律忽略，不回复。"""
    message = update.get("message") or update.get("channel_post")
    if not message:
        return

    text = str(message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not text.startswith("/") or chat_id is None:
        return

    # "/btcusdt" 或 "/btcusdt@your_bot_name" -> 取"/"后面、"@"前面、第一个空格前
    # 的那一段，当作要查询的币种代码。
    body = text[1:].split("@", 1)[0].split()[0].strip() if text[1:].strip() else ""

    if body.lower() in ("start", "help", ""):
        send_message(chat_id, "输入 /币种 查询该币种最近的信号，例如：/btcusdt")
        return

    results = query_signals(body)
    send_message(chat_id, format_reply(body, results))


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