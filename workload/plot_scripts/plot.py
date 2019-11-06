import sys, json, datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

if len(sys.argv) < 2:
	print "usage: %s <workload_file>" % sys.argv[0]
	sys.exit(1)

filename = sys.argv[1]
fp = open(filename)
line = fp.readline()
spawn_boot_shutdown_times = dict()
heartbeats = dict()
vm_runtimes = dict()
while line:
	tokens = line.split(" - ")
	if "EVENT" in line:
		try:
			event_data = tokens[2].replace("EVENT: ", "")
			json_data = json.loads(event_data)
			vm_seq_num = json_data['vm_seq_num']
			event_type = json_data['event']
			event_time = datetime.datetime.strptime(json_data['time'], "%Y-%m-%d.%X")

			if event_type == "boot":
				spawn_boot_shutdown_times[vm_seq_num].append(long(event_time.strftime("%s")))
			elif event_type == "shutdown":
				spawn_boot_shutdown_times[vm_seq_num].append(long(event_time.strftime("%s")))
			elif event_type == "spawn":
				if not vm_seq_num in spawn_boot_shutdown_times:
					spawn_boot_shutdown_times[vm_seq_num] = []
#				event_time = event_time + datetime.timedelta(hours=-3) ## this was Athens timezone
				spawn_boot_shutdown_times[vm_seq_num].append(long(event_time.strftime("%s")))
			elif event_type == "heartbeat":
				if not vm_seq_num in heartbeats:
					heartbeats[vm_seq_num] = []
				heartbeats[vm_seq_num].append(long(event_time.strftime("%s")))
		except ValueError:
			print "ERROR in line: ", line
			pass
	elif "Spawned new VM" in line:
		vm_name = tokens[2].split()[8]
		vm_seq_num = int(tokens[2].split()[5])
		vm_runtime = int(vm_name.split('-')[-1]) if "fixed_time" in vm_name else 0
		vm_runtimes[vm_seq_num] = vm_runtime

	line = fp.readline()

ax = plt.subplot("111")
for k in spawn_boot_shutdown_times:
	ax.plot(spawn_boot_shutdown_times[k][0], [k], 'bx')
	ax.plot(spawn_boot_shutdown_times[k][1], [k], 'yx')
	ax.plot(spawn_boot_shutdown_times[k][2], [k], 'gx')
	ax.text(spawn_boot_shutdown_times[k][2]+100, k, str(vm_runtimes[k]))
#	ax.plot(heartbeats[k], [k] * len(heartbeats[k]), 'yo')
plt.savefig("boot_times.png", bbox_inches = 'tight')
