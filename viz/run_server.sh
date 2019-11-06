#!/bin/bash

function finish {
	echo "Killing vizualize.py command (PID ${vizualize_pid})"
	kill -9 ${vizualize_pid}
	echo "Exiting..."
	exit 1
}

trap finish EXIT

python ./vizualize.py &
vizualize_pid=$!
#python -m SimpleHTTPServer 8081
php -S 0.0.0.0:8081 -t .
