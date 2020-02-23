#!/bin/bash

while true; do
        echo -n "$(date +%T) " >> /root/stress-metrics.txt
        stress-ng -c 2 --metrics-brief -t 20 2>&1 | grep "] cpu" | rev | awk '{print $2}' | rev >> /root/stress-metrics.txt
done;
