#!/bin/bash

SILVER_ID_BASE=100
GOLD_ID_BASE=1000
RAM_PER_VCPU=2048 # MB
DISK=15  # GB

case $1 in
"create")
	for vcpus in 1 2 4 8; do
		RAM=$((${RAM_PER_VCPU} * ${vcpus}))
		bname="acticloud.${vcpus}core"
		echo "Creating $bname gold and silver flavors"
		openstack flavor create --vcpus $vcpus --ram $RAM --disk $DISK $bname.silver --id $(($SILVER_ID_BASE + $vcpus))
		openstack flavor create --vcpus $vcpus --ram $RAM --disk $DISK $bname.gold --id $(($GOLD_ID_BASE + $vcpus))
	done
	;;
"delete")
	for vcpus in 1 2 4 8; do
		bname="acticloud.${vcpus}core"
		echo "Deleting $bname gold and silver flavors"
		openstack flavor delete $bname.silver
		openstack flavor delete $bname.gold
	done
	;;
*)
	echo "usage: $0 [ create | delete ]"
	;;
esac
