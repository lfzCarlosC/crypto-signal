import asyncio
import ccxt.async_support as ccxt

symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'LTC/USDT']
batch_size = 2

async def fetch_symbol_ohlcv(exchange, symbol):
    try:
        print("=======")
        print(symbol)
        data = await exchange.fetch_ohlcv(['BTC/USDT', 'ETH/USDT'], timeframe='1m', limit=100)
        print(f"{symbol}  OK")
        return symbol, data
    except Exception as e:
        print(f"{symbol} Error: {e}")
        return symbol, []

async def main():
    exchange = ccxt.bitget()
    await exchange.load_markets()

    results = []

    for i in range(0, len(symbols), batch_size):  # 注意：这里要顶格缩进，4空格
        batch = symbols[i:i + batch_size]
        print(f" 处理第 {i // batch_size + 1} 批: {batch}")

        tasks = [fetch_symbol_ohlcv(exchange, s) for s in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

        await asyncio.sleep(1)  # 限速防ban

    await exchange.close()
    return results

# 执行主函数
results = asyncio.run(main())
