# Cryptal Ark v3.0

Cryptal Ark is a trend detecting tool for your crypto currency Technical Analysis (TA).

Track all coins across man stream exchanges Bittrex, Bitfinex, Binance, Huobipro, Okex, kucoin, ZB and more!

Technical Analysis Automated:
* Momentum
* Relative Strength Index (RSI)
* Ichimoku Cloud (Leading Span A, Leading Span B, Conversion Line, Base Line)
* Simple Moving Average
* Exponential Moving Average
* MACD(Divergence) (V2.0) 
* MFI
* OBV
* VWAP
* KDJ(V2.0)
* DMI(V2.0)
* TD(V2.0)
* RSI
* Triangle breakthrough(super-advanced for trending analysis) :)

* Strategies by combining/tweaking certain indicators.

Alerts:
* SMS via Twilio
* Email
* Slack
* Telegram
* Discord

Features:
* Modular code for easy trading strategy implementation
* Easy install with Docker

## v2.0(Konig)
* support more powerful and practical indicators and tuning
* refine notification system(refine gmail, add DingTalk)

## v3.0(Mark XLIV)
![image](https://github.com/lfzCarlosC/crypto-signal/blob/master/markxliv.jpeg)
* api for submitting job to execute strategy 
   1. job framework(done)
   2. add redis to store signal(done)
   3. explore frontend tech for building a dashboard(maybe postponed as the requirement is not really necessary)
* strategic level change of using timeLevel resonance(done)

## v4.0
* as a popular exchange called FTX increases more and more items to be tradable(tokenized stocks), it is necessary for cryptal-signal to support FTX

![image](https://github.com/lfzCarlosC/crypto-signal/blob/master/api/arch.jpg)

## future consideration
* dockerize each running instance
* kafka to store job parameters

You can build on top of this tool and implement algorithm trading and some machine learning models to experiment with predictive analysis.


## Installing And Running
The commands listed below are intended to be run in a terminal.

1. Install [docker CE](https://docs.docker.com/install/)

1. Create a config.yml file in your current directory. See the Configuring config.yml section below for customizing settings.

1. In a terminal run the application. `docker run --rm -v $PWD/config.yml:/app/config.yml shadowreaver/crypto-signal:master`.

1. When you want to update the application run `docker pull shadowreaver/crypto-signal:master`

(you have to update the latest ccxt version)

### Configuring config.yml

For a list of all possible options for config.yml and some example configurations look [here](docs/config.md)

# FAQ

## Common Questions

### Why does Tradingview show me different information than crypto-signal?
There are a number of reasons why the information crypto-signal provides could be different from tradingview and the truth is we have no way to be 100% certain of why the differences exist. Below are some things that affect the indicators that _may_ differ between crypto-signal and tradingview.

- tradingview will have more historical data and for some indicators this can make a [big difference](https://ta-lib.org/d_api/ta_setunstableperiod.html).

- tradingview uses a rolling 15 minute timeframe which means that the data they are analyzing can be more recent than ours by a factor of minutes or hours depending on what candlestick timeframe you are using.

- tradingview may collect data in a way that means the timeperiods we have may not line up with theres, which can have an effect on the analysis. This seems unlikely to us, but stranger things have happened.

### So if it doesn't match Tradingview how do you know your information is accurate?
Underpinning crypto-signal for most of our technical analysis is [TA-Lib](https://ta-lib.org/index.html) which is an open source technical analysis project started in 1999. This project has been used in a rather large number of technical analysis projects over the last two decades and is one of the most trusted open source libraries for analyzing candlestick data.

# Liability
I am not your financial adviser, nor is this tool. Use this program as an educational tool, and nothing more. None of the contributors to this project are liable for any losses you may incur. Be wise and always do your own research.
This project just uses CryptoSignal/crypto-signal(which has MTL license) to retrieve ohlcv data.
It also keeps those indicators in CryptoSignal/crypto-signal but they are not used.
