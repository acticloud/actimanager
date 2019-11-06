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
time_axis = [0]     ## The time axis
nr_vcpus_axis = [0] ## Accumulative sum of vcpus active on the DC
seq_num_to_vcpus = dict()
previous_epoch = 0
first_vm_boot_epoch = 0
nr_errors = 0
periodic_check_epochs = [0]
line = fp.readline()
while line:
	tokens = line.split(" - ")
	if "EVENT" in line:
		try:
			event_data = tokens[2].replace("EVENT: ", "")
			json_data = json.loads(event_data)
			if not 'vm_seq_num' in json_data:
				line = fp.readline()
				continue
			vm_seq_num = json_data['vm_seq_num']
			event_type = json_data['event']
			event_time = datetime.datetime.strptime(json_data['time'], "%Y-%m-%d.%X")
			event_epoch = long(event_time.strftime("%s"))

			if event_type == "boot" or event_type == "shutdown":
				if event_type == "boot":
					new_nr_vcpus = nr_vcpus_axis[-1] + seq_num_to_vcpus[vm_seq_num]
				else:
					new_nr_vcpus = nr_vcpus_axis[-1] - seq_num_to_vcpus[vm_seq_num]
				nr_vcpus_axis.append(new_nr_vcpus)
				if (previous_epoch == 0):
					time_axis.append(1)
					first_vm_boot_epoch = event_epoch
				else:
					time_axis.append(time_axis[-1] + event_epoch - previous_epoch + 1)
				previous_epoch = event_epoch
			elif event_type == "spawn":
				## Here we read the number of vcpus for later use
				seq_num_to_vcpus[vm_seq_num] = json_data['vcpus']
		except ValueError:
			if "vm_seq_num" in line:
				nr_errors += 1
			pass
	elif "---> Periodic checking" in line:
		event_time = datetime.datetime.strptime(tokens[0], "%Y-%m-%d.%X")
		event_epoch = long(event_time.strftime("%s"))
		if (first_vm_boot_epoch):
			periodic_check_epochs.append(event_epoch - first_vm_boot_epoch + 1)
	line = fp.readline()

print "ERRONEOUS LINES: ", nr_errors
time_axis = map(lambda x: x / 60.0, time_axis)  ## Turn seconds to minutes
ax = plt.subplot("111")
ax.step(time_axis, nr_vcpus_axis)

## Print vertical lines to indicate the periodic DC utilization checks
periodic_check_epochs = map(lambda x: x / 60.0, periodic_check_epochs)  ## Turn seconds to minutes
for p in periodic_check_epochs:
	plt.axvline(x=p, linestyle="--", linewidth=0.4, color="green")

plt.title(filename)
plt.xticks(np.arange(min(time_axis), max(time_axis)+1, 10))
plt.savefig("boot_times.png", bbox_inches = 'tight')
