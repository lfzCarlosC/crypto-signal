from flask import Flask, request #导入后端框架
import json
import ccxt #导入开单工具
import time
bn = ccxt.binance({
    "apiKey": 'API接口',
    "secret": 'API密钥',
    'enableRateLimit': True,
    "timeout": 3000,
    "enableRateLimit": False
    })

#开单函数（这里是Binance Api接口的程序）
def do(data):
    try:
        symbol = data['symbol'].replace('PERP','') 
        side = data['side']
        amount = float(format(float(data['amount']),'.%sf' % data['point']))
        if side=='buy':
            bn.fapiPrivatePostOrder({"symbol": symbol,"side": "BUY","type": "MARKET", "quantity": amount, 'reduceOnly':'false', "timestamp": int(time.time()*1000)})
        else:
            bn.fapiPrivatePostOrder({"symbol": symbol,"side": "SELL","type": "MARKET", "quantity": amount, 'reduceOnly':'false', "timestamp": int(time.time()*1000)})
        return
    except Exception as e: print(e)

app = Flask(__name__)
def after_request(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp
app.after_request(after_request)
@app.route("/open",methods=['POST'])
def open1():
    data = json.loads(request.data)
    do(data)
    return '1'
if __name__ == '__main__':
    app.run('0.0.0.0', 80) #端口接入