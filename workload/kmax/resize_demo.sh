#!/bin/bash

source /root/.adminrc
vcpus=$(nproc --all)

/root/stress.sh &

while true; do
        [ $(uptime | awk '{print $9}' | cut -c 1) -ge $(( 2 * $vcpus))  ] && \
        openstack server resize --flavor acticloud.2core.gold 1core.gold-1 && \
        pkill stress.sh && pkill -SIGINT stress-ng && exit 0
        sleep 60
done
