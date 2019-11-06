#!/bin/bash

replace_nova_conf()
{
	which_one=$1 ## Can be one of openstack, gps, gno, actimanager
	cp ../actimanager/openstack_components/conf/nova.${which_one}.conf /etc/nova/nova.conf
	chown nova:nova /etc/nova/nova.conf
	/etc/init.d/nova-scheduler restart
}

run_openstack()
{
	gold_ratio=$1
	noisy_ratio=$2
	initial_vcpus=$3
	rate=$4

	replace_nova_conf "openstack"

	echo "Executing openstack benchmark for ${gold_ratio}% gold, ${noisy_ratio}% noisy, ${initial_vcpus} initial vcpus and rate ${rate}"
	output_file="0.vanilla_openstack-spec-${gold_ratio}_gold-${noisy_ratio}_noisy-${initial_vcpus}_vcpus-${rate}_rate.${ITER}.txt"  
	python execute.py ${gold_ratio} ${noisy_ratio} 200 ${initial_vcpus} ${rate} &> results/${output_file}
}

run_gps_or_gno()
{
	gold_ratio=$1
	noisy_ratio=$2
	initial_vcpus=$3
	rate=$4
	gps_or_gno=$5
	number=$6

	replace_nova_conf ${gps_or_gno}

	base_filename="${number}.${gps_or_gno}-spec-${gold_ratio}_gold-${noisy_ratio}_noisy-${initial_vcpus}_vcpus-${rate}_rate"
	suffix="${ITER}.txt"

	## Start ACTiManager.internal daemons
	internal_pids=""
	for i in 1 2 3 4; do
		output_file="${base_filename}.internal-acticloud$i.${suffix}"
		python ../actimanager/Internal.py acticloud$i ${gps_or_gno} &> results/${output_file} &
		internal_pids="${internal_pids} $!"
	done

	echo "Executing ${gps_or_gno} benchmark for ${gold_ratio}% gold, ${noisy_ratio}% noisy, ${initial_vcpus} initial vcpus and rate ${rate}"
	output_file="${base_filename}.${suffix}"
	python execute.py ${gold_ratio} ${noisy_ratio} 200 ${initial_vcpus} ${rate} &> results/${output_file}

	sleep 30
	echo "killing ACTiManager.internal daemons with pids: $internal_pids"
	kill -9 $internal_pids
}

run_actimanager()
{
	gold_ratio=$1
	noisy_ratio=$2
	initial_vcpus=$3
	rate=$4
	flavor=$5
	number=$6

	replace_nova_conf "actimanager"

	base_filename="${number}.${flavor}-spec-${gold_ratio}_gold-${noisy_ratio}_noisy-${initial_vcpus}_vcpus-${rate}_rate"
	suffix="${ITER}.txt"

	## Start ACTiManager.external daemon
	output_file="${base_filename}.external.${suffix}"
	python ../actimanager/External.py &> results/${output_file} &
	external_pid=$!

	## Start ACTiManager.internal daemons
	internal_pids=""
	for i in 1 2 3 4; do
		output_file="${base_filename}.internal-acticloud$i.${suffix}"
		python ../actimanager/Internal.py acticloud$i $flavor &> results/${output_file} &
		internal_pids="${internal_pids} $!"
	done

	echo "Executing $flavor benchmark for ${gold_ratio}% gold, ${noisy_ratio}% noisy, ${initial_vcpus} initial vcpus and rate ${rate}"
	output_file="${base_filename}.${suffix}"
	python execute.py ${gold_ratio} ${noisy_ratio} 200 ${initial_vcpus} ${rate} &> results/${output_file}

	sleep 30
	echo "killing ACTiManager.internal and ACTiManager.external daemons with pids: ${internal_pids} and ${external_pid}"
	kill -9 $internal_pids $external_pid
}

clear_openstack_vms()
{
	echo "Deleting all openstack VMs"
	for i in `openstack server list -f value -c ID`; do openstack server delete $i; done
	sleep 10
}

## On exit kill all background jobs
on_exit()
{
	echo -n "killing all background jobs ($(jobs -p | tr '\n' ' ')) before exiting..."
	kill $(jobs -p)
}
trap on_exit EXIT

clear_openstack_vms

################################################################################
## 1. Different data center load scenarios
################################################################################
echo "=====> 1. Different data center load scenarios"
gold_ratio=20
noisy_ratio=50
vcpus_rates="30_8 60_6 120_4"
for iteration in "0"; do
	export ITER=$iteration

	for vcpus_rate in $vcpus_rates; do
		initial_vcpus=$(echo $vcpus_rate | cut -d'_' -f1)
		rate=$(echo $vcpus_rate | cut -d'_' -f2)

		run_openstack $gold_ratio $noisy_ratio $initial_vcpus $rate
		sleep 30
		run_gps_or_gno $gold_ratio $noisy_ratio $initial_vcpus $rate "gps" 1
		sleep 30
		run_gps_or_gno $gold_ratio $noisy_ratio $initial_vcpus $rate "gno" 2
		sleep 30
		run_actimanager $gold_ratio $noisy_ratio $initial_vcpus $rate "actistatic" 3
		sleep 30
		run_actimanager $gold_ratio $noisy_ratio $initial_vcpus $rate "actifull" 4
		sleep 30
	done
done
################################################################################

###############################################################################
# 2. Different gold/silver mixes
###############################################################################
echo "=====> 2. Different gold/silver mixes"
noisy_ratio=50
vcpus_rate="60_6"
initial_vcpus=$(echo $vcpus_rate | cut -d'_' -f1)
rate=$(echo $vcpus_rate | cut -d'_' -f2)
gold_ratios="0 50 100"
for iteration in "0"; do
	export ITER=$iteration

	for gold_ratio in $gold_ratios; do
		run_openstack $gold_ratio $noisy_ratio $initial_vcpus $rate
		sleep 30
		run_gps_or_gno $gold_ratio $noisy_ratio $initial_vcpus $rate "gps" 1
		sleep 30
		run_gps_or_gno $gold_ratio $noisy_ratio $initial_vcpus $rate "gno" 2
		sleep 30
		run_actimanager $gold_ratio $noisy_ratio $initial_vcpus $rate "actistatic" 3
		sleep 30
		run_actimanager $gold_ratio $noisy_ratio $initial_vcpus $rate "actifull" 4
		sleep 30
	done
done
###############################################################################

###############################################################################
# 3. Different noisy/quite mixes
###############################################################################
echo "=====> 3. Different noisy/quite mixes"
gold_ratio=20
vcpus_rate="60_6"
initial_vcpus=$(echo $vcpus_rate | cut -d'_' -f1)
rate=$(echo $vcpus_rate | cut -d'_' -f2)
noisy_ratios="20 80"
for iteration in "0"; do
	export ITER=$iteration

	for noisy_ratio in $noisy_ratios; do
		run_openstack $gold_ratio $noisy_ratio $initial_vcpus $rate
		sleep 30
		run_gps_or_gno $gold_ratio $noisy_ratio $initial_vcpus $rate "gps" 1
		sleep 30
		run_gps_or_gno $gold_ratio $noisy_ratio $initial_vcpus $rate "gno" 2
		sleep 30
		run_actimanager $gold_ratio $noisy_ratio $initial_vcpus $rate "actistatic" 3
		sleep 30
		run_actimanager $gold_ratio $noisy_ratio $initial_vcpus $rate "actifull" 4
		sleep 30
	done
done
###############################################################################
