. ~/.bash_profile

#activate conda env
source ~/miniconda3/bin/activate

ps aux | grep app.py | awk '{print $2}' | xargs kill -9

#update username locally
#find custom/*.yml -type f -exec sed -i '' -e "s/lfz.carlos/cryptalsender/" {} \;
#find easy/*.yml -type f -exec sed -i '' -e "s/lfz.carlos/cryptalsender/" {} \;

#update emails run locally
#python3 app/updateCoinList.py binance.sh easy/binance_1h_easy.yml 
#rm -rf *easyFileName

export modes=(custom)
cat /dev/null > h${modes[i]}.log
cat /dev/null > d${modes[i]}.log
cat /dev/null > w${modes[i]}.log

read -p 'run level: (1h(30min/4h or 1M)' runlevel
read -p 'run package(1d/3d/12h/1w): (y/n)' runpackage

#flush redis
redis-cli FLUSHALL

for(( i=0;i<${#modes[@]};i++)); do
#1h
    if [ "$runlevel" == "1h" ]
    then
        nohup python3 app/app.py  ${modes[i]}/binance_1h_${modes[i]}.yml ${modes[i]}/binance_1h.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_1h_${modes[i]}.yml ${modes[i]}/binance_1h.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_4h_${modes[i]}.yml ${modes[i]}/binance_4h.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_4h_${modes[i]}.yml ${modes[i]}/bitget_4h.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_2h_${modes[i]}.yml ${modes[i]}/bitget_2h.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        
    fi

    if [ "$runpackage"  == "y" ]
    then
        nohup python3 app/app.py  ${modes[i]}/binance_6h_${modes[i]}.yml ${modes[i]}/binance_6h.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_12h_${modes[i]}.yml ${modes[i]}/binance_12h.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_d_${modes[i]}.yml ${modes[i]}/binance_d.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_3d_${modes[i]}.yml ${modes[i]}/binance_3d.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_w_${modes[i]}.yml ${modes[i]}/binance_w.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &

        #python3 app/app.py  ${modes[i]}/mexc_12h_custom.yml ${modes[i]}/mexc_12h.log ${modes[i]}  -a &
        #python3 app/app.py  ${modes[i]}/mexc_d_custom.yml ${modes[i]}/mexc_d.log ${modes[i]}  -a &
        #python3 app/app.py  ${modes[i]}/mexc_3d_custom.yml ${modes[i]}/mexc_3d.log ${modes[i]}  -a &
        #python3 app/app.py  ${modes[i]}/mexc_w_custom.yml ${modes[i]}/mexc_w.log ${modes[i]}  -a &

        nohup python3 app/app.py  ${modes[i]}/bitget_12h_custom.yml ${modes[i]}/bitget_12h.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup  python3 app/app.py  ${modes[i]}/bitget_d_custom.yml ${modes[i]}/bitget_d.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_6h_custom.yml ${modes[i]}/bitget_6h.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_3d_custom.yml ${modes[i]}/bitget_3d.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_w_custom.yml ${modes[i]}/bitget_w.log ${modes[i]}  -a > ${modes[i]}/system.out 2>&1 &

 #       python3 app/app.py  ${modes[i]}/gate_w_custom.yml ${modes[i]}/gate_w.log ${modes[i]}  -a &
#        python3 app/app.py  ${modes[i]}/hitbtc_d_${modes[i]}.yml ${modes[i]}/hitbtc_d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/hitbtc_w_${modes[i]}.yml ${modes[i]}/hitbtc_w.log ${modes[i]} -a &

#        python3 app/app.py  ${modes[i]}/coinex_12h_${modes[i]}.yml ${modes[i]}/coinex_12h.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/coinex_d_${modes[i]}.yml ${modes[i]}/coinex_d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/coinex_3d_${modes[i]}.yml ${modes[i]}/coinex_3d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/coinex_w_${modes[i]}.yml ${modes[i]}/coinex_w.log ${modes[i]} -a &

#        python3 app/app.py  ${modes[i]}/poloniex_12h_${modes[i]}.yml ${modes[i]}/poloniex_12h.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/poloniex_d_${modes[i]}.yml ${modes[i]}/poloniex_d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/poloniex_3d_${modes[i]}.yml ${modes[i]}/poloniex_3d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/poloniex_w_${modes[i]}.yml ${modes[i]}/poloniex_w.log ${modes[i]} -a &

#        python3 app/app.py  ${modes[i]}/huobi_4h_${modes[i]}.yml ${modes[i]}/huobi_4h.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/huobi_d_${modes[i]}.yml ${modes[i]}/huobi_d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/huobi_w_${modes[i]}.yml ${modes[i]}/huobi_w.log ${modes[i]} -a &

        # nohup python3 app/app.py  ${modes[i]}/okex_6h_${modes[i]}.yml ${modes[i]}/okex_6h.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        # nohup python3 app/app.py  ${modes[i]}/okex_12h_${modes[i]}.yml ${modes[i]}/okex_12h.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        # nohup python3 app/app.py  ${modes[i]}/okex_d_${modes[i]}.yml ${modes[i]}/okex_d.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
        # nohup python3 app/app.py  ${modes[i]}/okex_w_${modes[i]}.yml ${modes[i]}/okex_w.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &

        #python3 app/app.py  ${modes[i]}/gateio_4h_${modes[i]}.yml ${modes[i]}/gateio_4h.log ${modes[i]} -a &
        #python3 app/app.py  ${modes[i]}/gateio_6h_${modes[i]}.yml ${modes[i]}/gateio_6h.log ${modes[i]} -a &
        #python3 app/app.py  ${modes[i]}/gateio_12h_${modes[i]}.yml ${modes[i]}/gateio_12h.log ${modes[i]} -a &
        #python3 app/app.py  ${modes[i]}/gateio_w_${modes[i]}.yml ${modes[i]}/gateio_w.log ${modes[i]} -a &

#    python3 app/app.py  ${modes[i]}/kucoin_1h_${modes[i]}.yml ${modes[i]}/kucoin_1h.log ${modes[i]} -a &
#    python3 app/app.py  ${modes[i]}/kucoin_4h_${modes[i]}.yml ${modes[i]}/kucoin_4h.log ${modes[i]} -a &
        #python3 app/app.py  ${modes[i]}/kucoin_d_${modes[i]}.yml ${modes[i]}/kucoin_d.log ${modes[i]}  -a &
        #python3 app/app.py  ${modes[i]}/kucoin_w_${modes[i]}.yml ${modes[i]}/kucoin_w.log ${modes[i]} -a &

#   python3 app/app.py  ${modes[i]}/bittrex_1h_${modes[i]}.yml ${modes[i]}/bittrex_1h.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/bittrex_1d_${modes[i]}.yml ${modes[i]}/bittrex_1d.log ${modes[i]} -a &

#    #python3 app/app.py  ${modes[i]}/bitfinex_1h_${modes[i]}.yml ${modes[i]}/bitfinex_1h.log ${modes[i]} -a &
#    #python3 app/app.py  ${modes[i]}/bitfinex_6h_${modes[i]}.yml ${modes[i]}/bitfinex_6h.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/bitfinex_d_${modes[i]}.yml  ${modes[i]}/bitfinex_d.log ${modes[i]} -a &
#        python3 app/app.py  ${modes[i]}/bitfinex_w_${modes[i]}.yml ${modes[i]}/bitfinex_w.log ${modes[i]} -a &

    fi
    
#Monthly
    if [ "$runlevel" == "1M" ]
    then
        python3 app/app.py  ${modes[i]}/binance_M_${modes[i]}.yml ${modes[i]}/binance_M.log ${modes[i]} -a &
    fi

    #contract
 #   python3 app/app.py  ${modes[i]}/okex_1h_${modes[i]}_contract.yml ${modes[i]}/okex_1h_contract.log ${modes[i]} &
 #   python3 app/app.py  ${modes[i]}/okex_30min_${modes[i]}_contract.yml ${modes[i]}/okex_30min_contract.log ${modes[i]} &
 #   python3 app/app.py  ${modes[i]}/okex_4h_${modes[i]}_contract.yml ${modes[i]}/okex_4h_contract.log ${modes[i]} &
 #   python3 app/app.py  ${modes[i]}/okex_1d_${modes[i]}_contract.yml ${modes[i]}/okex_1d_contract.log ${modes[i]} &
 #   python3 app/app.py  ${modes[i]}/okex_15min_${modes[i]}_contract.yml ${modes[i]}/okex_15min_contract.log ${modes[i]} &
done

java -jar api/out/artifacts/cryptal_signal_api_jar/cryptal-signal.api.jar &

python3 -m venv venv
/bin/sh -c ". venv/bin/activate; exec sh -c 'pip3 install Werkzeug==2.0.3; pip3 install mysqlclient; export FLASK_APP=superset; superset run -p 8088 --with-threads --reload --debugger'"
