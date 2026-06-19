. ~/.bash_profile

#git upudate
git reset --hard 
git fetch upstream
git pull

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
read -p 'run all coin? (y/n)' runallcoins

#flush redis
redis-cli FLUSHALL

for(( i=0;i<${#modes[@]};i++)); do
#1h
    if [ "$runlevel" == "1h" ]
    then
        nohup python3 app/app.py  ${modes[i]}/binance_15min_${modes[i]}.yml ${modes[i]}/binance_15min.log ${modes[i]}  > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_30min_${modes[i]}.yml ${modes[i]}/binance_30min.log ${modes[i]}  > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_1h_${modes[i]}.yml ${modes[i]}/okex_1h.log ${modes[i]}   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_1h_${modes[i]}.yml ${modes[i]}/bitget_1h.log ${modes[i]}  > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_2h_${modes[i]}.yml ${modes[i]}/bitget_2h.log ${modes[i]}  > ${modes[i]}/system.out 2>&1 &
        
        nohup python3 app/app.py  ${modes[i]}/okex_4h_${modes[i]}.yml ${modes[i]}/okex_4h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_6h_${modes[i]}.yml ${modes[i]}/okex_6h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_12h_${modes[i]}.yml ${modes[i]}/okex_12h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        
        nohup python3 app/app.py  ${modes[i]}/binance_6h_${modes[i]}.yml ${modes[i]}/binance_6h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_12h_${modes[i]}.yml ${modes[i]}/binance_12h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_4h_${modes[i]}.yml ${modes[i]}/binance_4h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &

        nohup python3 app/app.py  ${modes[i]}/bitget_12h_custom.yml ${modes[i]}/bitget_12h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_4h_custom.yml ${modes[i]}/bitget_4h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_6h_custom.yml ${modes[i]}/bitget_6h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        
    fi

    if [ "$runpackage"  == "y" ]
    then
        nohup python3 app/app.py  ${modes[i]}/binance_d_${modes[i]}.yml ${modes[i]}/binance_d.log ${modes[i]} > ${modes[i]}/system_binance_d.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_3d_${modes[i]}.yml ${modes[i]}/binance_3d.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_w_${modes[i]}.yml ${modes[i]}/binance_w.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_12h_${modes[i]}.yml ${modes[i]}/binance_12h.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/binance_M_${modes[i]}.yml ${modes[i]}/binance_M.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &

        nohup python3 app/app.py  ${modes[i]}/bitget_d_${modes[i]}.yml ${modes[i]}/bitget_d.log ${modes[i]}   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_3d_${modes[i]}.yml ${modes[i]}/bitget_3d.log ${modes[i]}   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_w_${modes[i]}.yml ${modes[i]}/bitget_w.log ${modes[i]}   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_12h_${modes[i]}.yml ${modes[i]}/bitget_12h.log ${modes[i]}   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_M_${modes[i]}.yml ${modes[i]}/bitget_M.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &

        nohup python3 app/app.py  ${modes[i]}/okex_12h_${modes[i]}.yml ${modes[i]}/okex_12h.log ${modes[i]}   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_d_${modes[i]}.yml ${modes[i]}/okex_d.log ${modes[i]}  > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_w_${modes[i]}.yml ${modes[i]}/okex_w.log ${modes[i]}  > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_M_${modes[i]}.yml ${modes[i]}/okex_M.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/okex_3M_${modes[i]}.yml ${modes[i]}/okex_3M.log ${modes[i]} > ${modes[i]}/system.out 2>&1 &
    fi

    if [ "$runallcoins"  == "y" ]
    then
#        nohup python3 app/app.py  ${modes[i]}/binance_3d_${modes[i]}.yml ${modes[i]}/binance_3d.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
#        nohup python3 app/app.py  ${modes[i]}/binance_w_${modes[i]}.yml ${modes[i]}/binance_w.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
#        nohup python3 app/app.py  ${modes[i]}/binance_M_${modes[i]}.yml ${modes[i]}/binance_M.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &

        nohup python3 app/app.py  ${modes[i]}/bitget_3d_${modes[i]}.yml ${modes[i]}/bitget_3d.log ${modes[i]} -a   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_w_${modes[i]}.yml ${modes[i]}/bitget_w.log ${modes[i]} -a   > ${modes[i]}/system.out 2>&1 &
        nohup python3 app/app.py  ${modes[i]}/bitget_M_${modes[i]}.yml ${modes[i]}/bitget_M.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &

#        nohup python3 app/app.py  ${modes[i]}/okex_w_${modes[i]}.yml ${modes[i]}/okex_w.log ${modes[i]} -a  > ${modes[i]}/system.out 2>&1 &
#        nohup python3 app/app.py  ${modes[i]}/okex_M_${modes[i]}.yml ${modes[i]}/okex_M.log ${modes[i]} -a  > ${modes[i]}/system.out 2>&1 &
#        nohup python3 app/app.py  ${modes[i]}/okex_3M_${modes[i]}.yml ${modes[i]}/okex_3M.log ${modes[i]} -a > ${modes[i]}/system.out 2>&1 &
    fi
    
#Monthly
    if [ "$runlevel" == "1M" ]
    then
        python3 app/app.py  ${modes[i]}/binance_M_${modes[i]}.yml ${modes[i]}/binance_M.log ${modes[i]} -a &
    fi
done

python3 -m venv venv
nohup /bin/sh -c ". venv/bin/activate; \
pip3 install Werkzeug==2.0.3 mysqlclient; \
SECRET_KEY=\$(openssl rand -base64 42); \
echo \"SECRET_KEY = '\$SECRET_KEY'\" > superset_config.py; \
export SUPERSET_CONFIG_PATH=\$(pwd)/superset_config.py; \
export FLASK_APP=superset; \
superset run -p 8088 --with-threads --reload --debugger" >/dev/null 2>&1 &
