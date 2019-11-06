import random, re

benches = [

#	{"name": "stress-stream",
#	 "is_noisy": 1,
#	 "is_sensitive": 1,
#	 "run_mode": "fixed_time",
#	 "openstack_image": "acticloud-image"},
#
#	## Moved the load as a random choice in `get_vm_userdata()`
#	{"name": "stress-cpu",
#	 "is_noisy": 0,
#	 "is_sensitive": 0,
#	 "run_mode": "fixed_time",
#	 "openstack_image": "acticloud-image"},

	{"name": "spec-473.astar",
	 "is_noisy": 0,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 170}, ## The duration in seconds when run in isolation (1 vcpu)

	{"name": "spec-401.bzip2",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 126},

	{"name": "spec-410.bwaves",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 415},

	{"name": "spec-416.gamess",
	 "is_noisy": 0,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 61},

	{"name": "spec-429.mcf",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 274},

	{"name": "spec-433.milc",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 465},

	{"name": "spec-436.cactusADM",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 666},

	{"name": "spec-437.leslie3d",
	 "is_noisy": 0,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 325},

	{"name": "spec-444.namd",
	 "is_noisy": 0,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 458},

	{"name": "spec-445.gobmk",
	 "is_noisy": 0,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 81},

	{"name": "spec-453.povray",
	 "is_noisy": 0,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 184},

	{"name": "spec-454.calculix",
	 "is_noisy": 0,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 900},

	{"name": "spec-459.GemsFDTD",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 380},

	{"name": "spec-462.libquantum",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 358},

	{"name": "spec-465.tonto",
	 "is_noisy": 1,
	 "is_sensitive": 0,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 622},

	{"name": "spec-471.omnetpp",
	 "is_noisy": 1,
	 "is_sensitive": 1,
	 "run_mode": "to_completion",
	 "openstack_image": "acticloud-image",
	 "runtime_isolation": 322},

]

benches_per_category = []
benches_per_category.append([x for x in benches if x['is_noisy'] == 0])
benches_per_category.append([x for x in benches if x['is_noisy'] == 1])

## The code to execute on newly created VMs in order to put load on them
vm_user_data_header = \
"""#!/bin/bash
export VMUUID=$(basename $(readlink -f /var/lib/cloud/instance)) ## Get VM's Openstack UUID
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"boot\\" , \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
"""
vm_user_data_footer = \
"""
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"shutdown\\" , \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
shutdown -h now
exit 0
"""
vm_user_data_cpu = \
"""
shutdown +$((%(runtime)d+5)) ## Just in case timeout stucks
timeout %(runtime)d bash -c \
'
i=0
while [ 1 ]; do
{
stress-ng -c %(vcpus)d -l %(load)d --timeout %(report_interval)d --metrics-brief
i=$((i+1))
} &> /tmp/tosend
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"heartbeat\\", \
       \\"bench\\": \\"stress-cpu\\", \\"load\\": %(load)d, \\"vcpus\\": %(vcpus)d, \
       \\"output\\": \\"`cat /tmp/tosend | tr \\"\\n\\" \\";\\" | tr \\"\\\\"\\" \\"^\\"`\\", \
       \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
done
'
"""
vm_user_data_stream = \
"""
shutdown +$((%(runtime)d+5)) ## Just in case timeout stucks
timeout %(runtime)d bash -c \
'
i=0
while [ 1 ]; do
{
stress-ng --stream %(vcpus)d --timeout %(report_interval)d
sleep 10
i=$((i+1))
} &> /tmp/tosend
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"heartbeat\\", \
       \\"bench\\": \\"stress-stream\\", \\"vcpus\\": %(vcpus)d, \
       \\"output\\": \\"`cat /tmp/tosend | tr \\"\\n\\" \\";\\" | tr \\"\\\\"\\" \\"^\\"`\\", \
       \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
done
'
"""
### The following is used by calculix spec benchmark to fix the problem we have with
### the cslab_interpret_spec_cmd.py file inside the VM
vm_user_data_calculix_fix_spec_interpret_line = \
"""
cd /opt/spec-parsec-benchmarks/spec/
sed -i 's/if "-i" in sys.argv:/if "-i" in sys.argv and not "calculix" in sys.argv[5]:/g' cslab_interpret_spec_cmd.py
"""
vm_user_data_spec_to_completion = \
"""
cd /opt/spec-parsec-benchmarks/spec/
for t in `seq 0 $((%(times_to_run)d-1))`; do
{
echo "EXECUTION NUMBER $t"
for i in `seq 0 $((%(vcpus)d-2))`; do
	./cslab_run_specs_static.sh %(bench)s $i &
	sleep 5 ## add this small sleep here because some benchmarks (e.g., calculix) have problems when spawned alltogether
done
./cslab_run_specs_static.sh %(bench)s $((%(vcpus)d-1))
wait
} &> /tmp/tosend
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"heartbeat\\", \
       \\"bench\\": \\"spec-%(bench)s-to-completion\\", \\"vcpus\\": %(vcpus)d, \
       \\"output\\": \\"`cat /tmp/tosend | tr \\"\\n\\" \\";\\" | tr \\"\\\\"\\" \\"^\\"`\\", \
       \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
done
"""
vm_user_data_spec_fixed_time = \
"""
{
shutdown +$((%(runtime)d+5)) ## Just in case timeout stucks
cd /opt/spec-parsec-benchmarks/spec/
timeout %(runtime)d bash -c \
'
nr_executions=0
while [ 1 ]; do
	for i in `seq 0 $((%(vcpus)d-2))`; do
		./cslab_run_specs_static.sh %(bench)s $i &
	done
	./cslab_run_specs_static.sh %(bench)s $((%(vcpus)d-1))
	wait
	nr_executions=$(($nr_executions+1))
	echo NUMBER OF EXECUTIONS: $nr_executions
done
'
} &> /tmp/tosend
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"heartbeat\\", \
       \\"bench\\": \\"spec-%(bench)s-fixed-time\\", \\"vcpus\\": %(vcpus)d, \
       \\"output\\": \\"`cat /tmp/tosend | tr \\"\\n\\" \\";\\" | tr \\"\\\\"\\" \\"^\\"`\\", \
       \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
"""
vm_user_data_tailbench_fixed_time = \
"""
{
shutdown +$((%(runtime)d+5)) ## Just in case timeout stucks
echo "-----> START: `date` VM number: %(seq_num)d name: tailbench-%(benchname)s runs TAILBENCH %(benchname)s"
cd /home/ubuntu
timeout %(runtime)d bash -c \
'
nr_executions=0
while [ 1 ]; do
	NTHREADS=%(vcpus)d ./run-bench.sh %(benchname)s
	nr_executions=$(($nr_executions+1))
	echo NUMBER OF EXECUTIONS: $nr_executions
done
'
echo "-----> END: VM number %(seq_num)d"
} &> /tmp/tosend
echo "{\\"vm_uuid\\": \\"$VMUUID\\", \\"vm_seq_num\\": %(seq_num)d, \\"event\\": \\"heartbeat\\", \
       \\"bench\\": \\"tailbench-%(benchname)s-fixed-time\\", \\"vcpus\\": %(vcpus)d, \
       \\"output\\": \\"`cat /tmp/tosend | tr \\"\\n\\" \\";\\" | tr \\"\\\\"\\" \\"^\\"`\\", \
       \\"time\\": \\"`date +%%F.%%T`\\"}" | nc -N 10.0.0.8 8080
"""

## bench -> dict()
def bench_get_name(bench):
	if bench['name'] == "stress-cpu":
		load = random.choice([25, 50, 75, 100])
		bench['load'] = load
		return "stress-cpu-" + str(load)
	else:
		return bench['name']

## bench_name -> str, nvcpus -> int, output -> str
## returns float, the performance of the VM or -1 if the performance could not
## be obtained
def bench_get_perf_from_output(bench_name, nvcpus, output):
	ret = -1.0
	unit = "NULL"
	if bench_name == "stress-stream":
		memory_rate_entries = re.findall("memory rate: [0-9]*.[0-9]*", output)
		memory_rate_values = map(lambda x: float(x.split(':')[1]), memory_rate_entries)
		ret = sum(memory_rate_values) / len(memory_rate_values)
		unit = "throughput"
	elif "stress-cpu" in bench_name:
		bogoops_entry = re.findall("cpu +[0-9.]+ +[0-9.]+ +[0-9.]+ +[0-9.]+ +[0-9.]+ +[0-9.]+", output)[0]
		bogoops_value = bogoops_entry.split()[5]
		ret = bogoops_value
		unit = "throughput"
	elif "spec" in bench_name:
		seconds_entries = re.findall("[0-9]+ seconds", output)
		seconds_values = map(lambda x: float(x.split()[0]), seconds_entries)
		ret = sum(seconds_values) / len(seconds_values)
		unit = "time"
	else:
		pass
	return (ret, unit)

## seq_num -> int, vcpus -> int, bench -> dict(), runtime -> int
def get_vm_userdata(seq_num, vcpus, bench, runtime, times_to_run):
	bench_name = bench['name']
	bench_run_mode = bench['run_mode']

	report_interval = 1 * 60 # 1 minute
	runtime *= 60

	udata = vm_user_data_header % {"seq_num": seq_num}
	if bench_name == "stress-cpu":
		load = bench['load']
		udata += vm_user_data_cpu % {"seq_num": seq_num, "vcpus": vcpus,
		                             "runtime": runtime,
		                             "bench": bench, "load": load,
		                             "report_interval": report_interval}
	elif bench_name == "stress-stream":
		udata += vm_user_data_stream % {"seq_num": seq_num, "vcpus": vcpus,
		                               "runtime": runtime,
		                               "report_interval": report_interval}
	elif "spec-" in bench_name:
		if "calculix" in bench_name:
			udata += vm_user_data_calculix_fix_spec_interpret_line

		spec_bench = bench_name.split("-")[1]
		udata += vm_user_data_spec_to_completion % \
		                 {"seq_num": seq_num, "vcpus": vcpus,
		                  "times_to_run": times_to_run, "bench": spec_bench}
	elif "tailbench-" in bench_name:
		tailbench = bench_name.split("-")[1]
		udata += vm_user_data_tailbench_fixed_time % \
		             {"seq_num": seq_num, "vcpus": vcpus, "benchname": tailbench, \
		              "runtime": runtime}
	udata += vm_user_data_footer % {"seq_num": seq_num}
	return udata
