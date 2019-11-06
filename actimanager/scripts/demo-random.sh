#!/bin/bash

NR_VMS=16
GOLD_RATIO=40
CREATE_RATIO=90
GOLD_GROUP_ID="e942edc2-444e-4054-8632-9394d53432c4"
SILVER_GROUP_ID="ed5ac2ad-0e14-4260-8cd7-f0ddea410717"
FLAVOR="demo-tiny"
IMAGE="cirros-new"
DELAY=30

echo "Running Demo scenario with the following parameters:"
echo "Number of Total VMs: $NR_VMS"
echo "Proportion of Gold VMs: $GOLD_RATIO%"
echo "Proportion of Create VM: $CREATE_RATIO%"

next_gold_nr=1
next_silver_nr=1

for nvm in `seq 1 $NR_VMS`; do
	create_random=$((RANDOM % 100))
	gold_random=$((RANDOM % 100))

	if (( $create_random < $CREATE_RATIO )); then
		if (( $gold_random < $GOLD_RATIO )); then
			group_id=$GOLD_GROUP_ID
			name="gold-$next_gold_nr"
			next_gold_nr=$((next_gold_nr+1))
			vm_str="GOLD"
		else
			group_id=$SILVER_GROUP_ID
			name="silver-$next_silver_nr"
			next_silver_nr=$((next_silver_nr+1))
			vm_str="SILVER"
		fi

		echo "Creating $vm_str VM with name $name"
		os_cmd="openstack server create --hint group=$group_id --flavor $FLAVOR --image $IMAGE --nic none --availability-zone nova:compute-1 $name"
	else
		if (( $gold_random < $CREATE_RATIO )); then
			vm_number=$((RANDOM % $next_gold_nr))
			name="gold-$vm_number"
			vm_str="GOLD"
		else
			vm_number=$((RANDOM % $next_silver_nr))
			name="silver-$vm_number"
			vm_str="SILVER"
		fi
		echo "Deleting $vm_str VM with name $name"
		os_cmd="openstack server delete $name"
	fi

	$os_cmd
	sleep $DELAY
done
