import yfinance as yf
from stocksymbol import StockSymbol

ticker = 'AAPL'

data = yf.download(ticker)
print(data)

#apiKey = '2ff045eb-e1bc-4679-b1f8-3ca3c17d08a5'
#ss = StockSymbol(apiKey)
#print(ss.get_symbol_list(index='DJI'))
