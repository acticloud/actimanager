import sys, json, datetime, random, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

STRESS_CPU_ISOLATION = { 1: {25: 50.13,  50: 100.38, 75: 150.6, 100: 201.96},
                         2: {25: 100.27, 50: 200.35, 75: 301.3, 100: 403.72},
                         4: {25: 200.82, 50: 401.92, 75: 603.5, 100: 807.33},
                         8: {25: 406.11, 50: 803.13, 75: 1206.10, 100:1614.66} }
STRESS_STREAM_ISOLATION = { 1: 10727.72, 2: 9138.285, 4: 8414.2375, 8: 6808.85 }
SPEC_ISOLATION = { "473.astar": { 1: 169, 2: 182, 4: 186.75, 8: 219.375 } }

if len(sys.argv) < 2:
	print "usage: %s <executor_output_file>" % sys.argv[0]
	sys.exit(1)

filename = sys.argv[1]
fp = open(filename)
line = fp.readline()
gold_vms = []
vms_boot_time = dict()
vms_hosts = dict()
vms_names = dict()
vm_perfs_flat_gold = []
vm_perfs_flat_silver = []
while line:
	tokens = line.split(" - ")
	if "EVENT" in line:
		try:
			event_data = tokens[2].replace("EVENT: ", "")
			json_data = json.loads(event_data)
			vm_seq_num = json_data['vm_seq_num']
			event_type = json_data['event']
			event_time = datetime.datetime.strptime(json_data['time'], "%Y-%m-%d.%X")
			event_epoch = long(event_time.strftime("%s"))

			if event_type == "boot":
				vms_boot_time[vm_seq_num] = event_epoch
			elif event_type == "shutdown":
				pass
			elif event_type == "spawn":
				host = json_data['host']
				vms_hosts[vm_seq_num] = host
			elif event_type == "heartbeat":
				bench = json_data['bench']
				load = 0 if bench != "stress-cpu" else json_data['load']
				output = json_data['output']
				vcpus = json_data['vcpus']
				output_lines = output.split(';')
				perf = 0.0
				base_perf = 1.0
				if "stress-cpu" in bench:
					perf_line = output_lines[4]
					base_perf = STRESS_CPU_ISOLATION[vcpus][load]
					perf = float(perf_line.split()[8])
					perf = perf / base_perf
				elif "stress-stream" in bench:
					first_perf_line_index = 4
					base_perf = STRESS_STREAM_ISOLATION[vcpus]
					perf_sum = 0.0
					for j in range(vcpus):
						perf_line = output_lines[first_perf_line_index + j]
						perf = float(perf_line.split()[6])
						perf_sum += perf
					perf = perf_sum / vcpus
					perf = perf / base_perf
				elif "spec-" in bench:
				  	spec_name = bench.split("-")[1]
				  	base_perf = SPEC_ISOLATION[spec_name][vcpus]
				  	seconds_sum = 0.0
				  	seconds_samples = 0
				  	for l in output_lines:
				  		if "seconds" in l:
					  		seconds_sum += int(l.split()[0])
					  		seconds_samples += 1

					perf = base_perf / (seconds_sum / vcpus)

				if vm_seq_num in gold_vms:
					vm_perfs_flat_gold.append(perf)
				else:
					vm_perfs_flat_silver.append(perf)

		except ValueError:
			pass
	elif "Spawned new VM" in line:
		tokens = line.split()
		vm_seq_num = int(tokens[9])
		vm_name = tokens[12]
		if "gold" in vm_name:
			gold_vms.append(vm_seq_num)
		vms_names[vm_seq_num] = vm_name.split("-")[2] + "-" + vm_name.split("-")[3]
	elif "Workload file:" in line:
		workload_file = line.split()[7]

	line = fp.readline()

problematic_gold = [ x for x in vm_perfs_flat_gold if x < 0.8 ]
problematic_silver = [ x for x in vm_perfs_flat_silver if x < 0.25 ]
print "Total points: %d" % (len(vm_perfs_flat_gold) + len(vm_perfs_flat_silver))
print "Gold: %d ( %d problematic )" % (len(vm_perfs_flat_gold), len(problematic_gold))
print "Silver: %d ( %d problematic )" % (len(vm_perfs_flat_silver), len(problematic_silver))

ax = plt.subplot("111")
#ax.axhline(0.25)
ax.axhline(0.8)
ax.plot(np.arange(len(vm_perfs_flat_gold)), vm_perfs_flat_gold, 'bx', label="GOLD")
#ax.plot(np.arange(len(vm_perfs_flat_silver)), vm_perfs_flat_silver, 'ro', label="SILVER")
plt.legend()
plt.savefig("boot_times.png", bbox_inches = 'tight')
