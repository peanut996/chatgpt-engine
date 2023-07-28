#!/bin/bash
start=$(date +%s)
dir_path=$(cd "$(dirname "$0")" && pwd)

echo "##################################"
echo "###### PREPARE ENV ###############"
echo "##################################"

source $dir_path/env.sh

echo "##################################"
echo "###### KILL PROCESS ##############"
echo "##################################"

engine_pid=$(ps -ef | awk '/python main.py/{print $2}')

client_pid=$(ps -ef | awk '/chatgpt-bot/{print $2}')

proxy_pid=$(ps -ef | awk '/.\/proxy/{print $2}')

kill $proxy_pid

kill $client_pid

kill $engine_pid


echo "##################################"
echo "###### RUN proxy server ##########"
echo "##################################"


cd "$dir_path/../proxy" || exit
go build -ldflags '-w -s' -o $dir_path/proxy $dir_path/../proxy
chmod +x $dir_path/proxy

nohup $dir_path/proxy > /tmp/proxy.log &

echo "start proxy on port 8080 done"


echo "##################################"
echo "###### RUN engine server #########"
echo "##################################"


cd "$dir_path/../engine" || exit


source venv/bin/activate

pip install -r requirements.txt --upgrade

nohup python main.py -c ../etc/config.yaml > /tmp/engine.log &

echo "run engine success"

echo "##################################"
echo "###### RUN client ################"
echo "##################################"

cd "$dir_path/../client" || exit

$dir_path/build.sh

nohup $dir_path/chatgpt-bot -c ../etc/config.yaml > /tmp/client.log &

echo "start client done"

end=$(date +%s)
take=$(( end - start ))
echo "Bot started in ${take} seconds."