import sys, json, re, datetime, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SPEC_ISOLATION = { "400.perlbench": { 1: 193, 2: 194, 4: 194, 8: 204.5 },
				   "401.bzip2": { 1: 126, 2: 127, 4: 127.75, 8: 127 },
				   "403.gcc": { 1: 24, 2: 24, 4: 25, 8: 29.75 },
				   "410.bwaves": { 1: 415, 2: 425, 4: 435.5, 8: 450.25 },
				   "416.gamess": { 1: 61, 2: 216.5, 4: 369.75, 8: 144.875 },
				   "429.mcf": { 1: 274, 2: 304, 4: 366, 8: 176.75 }, # 4 threads killed
				   "433.milc": { 1: 465, 2: 565, 4: 599.25, 8: 636.75 },
				   "434.zeusmp": { 1: 428, 2: 439.5, 4: 469.25, 8: 487.125 },
				   "435.gromacs": { 1: 393, 2: 391, 4: 392.75, 8: 393 },
				   "436.cactusADM": { 1: 666, 2: 672.5, 4: 717, 8: 765.875},
				   "437.leslie3d": { 1: 325, 2: 343.5, 4: 362.5, 8: 393.625 },
				   "444.namd": { 1: 458, 2: 458.5, 4: 457, 8: 458 },
				   "445.gobmk": { 1: 81, 2: 83, 4: 84.5, 8: 83 },
				   "447.dealII": { 1: 373, 2: 379.5, 4: 382.25, 8: 384.75 },
				   "450.soplex": { 1: 133, 2: 160, 4: 169.5, 8: 218.125 },
				   "453.povray": { 1: 184, 2: 184, 4: 183, 8: 183 },
				   "456.hmmer": { 1: 152, 2: 152, 4: 152, 8: 151 },
				   "458.sjeng": { 1: 630, 2: 635, 4: 642.75, 8: 647.5 },
				   "459.GemsFDTD": { 1: 380, 2: 435.5, 4: 451.75, 8: 495.75 },
				   "462.libquantum": { 1: 358, 2: 415, 4: 460, 8: 505.75 },
				   "464.h264ref": { 1: 79, 2: 79, 4: 78, 8: 79 },
				   "465.tonto": { 1: 622, 2: 375.5, 4: 253, 8: 193.75 },
				   "470.lbm": { 1: 407, 2: 426, 4: 473.5, 8: 533 },
				   "471.omnetpp": { 1: 322, 2: 325, 4: 441.5, 8: 514.375 },
				   "473.astar": { 1: 169, 2: 182, 4: 186.75, 8: 219.375 },
				   "482.sphinx3": { 1: 630, 2: 626.5, 4: 629.75, 8: 678 },
				   "483.xalancbmk": { 1: 234, 2: 251.5, 4: 268.5, 8: 333.875 },
				   "454.calculix": { 1: 900, 2: 900, 4: 900, 8: 900 } }


if (len(sys.argv) <= 1):
	print "usage: %s <executor_output_file>" % sys.argv[0]
	sys.exit(1)

## { vm_uuid: [ [heartbeat_times], [heartbeat_value] ], ...}
per_vm_heartbeats = dict()

## { vm_uuid: [ [esd_report_times], [[vcpu0_esd, vcpu1_esd, ...], [esd_report2]] ] }
per_vm_esd_report = dict()

vm_seq_num_to_vm_name = dict()
vm_seq_num_to_vcpus = dict()
vm_uuid_to_vm_name = dict()
vm_uuid_to_vcpus = dict()

filename = sys.argv[1]
fp = open(filename)
line = fp.readline()
while line:
	if "Spawned new VM" in line:
		occurence = re.findall("seq_num: [0-9]+", line)[0]
		seq_num = int(occurence.replace("seq_num: ", ""))
		occurence = re.findall("name: [a-zA-Z0-9-_.]+", line)[0]
		vm_name = occurence.replace("name: ", "")
		tokens = vm_name.split("-")
		vm_name = tokens[3]
		vm_seq_num_to_vm_name[seq_num] = vm_name
	elif "EVENT" in line and "spawn" in line:
		json_str = line.split("EVENT: ")[1]
		json_data = json.loads(json_str)
		vm_seq_num = json_data['vm_seq_num']
		vm_vcpus = int(json_data['vcpus'])
		vm_seq_num_to_vcpus[vm_seq_num] = vm_vcpus
	elif "boot" in line:
		json_str = line.split("EVENT: ")[1]
		json_data = json.loads(json_str)
		vm_seq_num = json_data['vm_seq_num']
		vm_uuid = json_data['vm_uuid']
		vm_name = vm_seq_num_to_vm_name[vm_seq_num]
		vm_uuid_to_vm_name[vm_uuid] = vm_name
		vm_vcpus = vm_seq_num_to_vcpus[vm_seq_num]
		vm_uuid_to_vcpus[vm_uuid] = vm_vcpus

	if not "internal-esd-report" in line and not "heartbeat" in line:
		line = fp.readline()
		continue
		
	json_str = line.split("EVENT: ")[1]
	json_data = json.loads(json_str)

	
	event_type = json_data['event']
	event_time = datetime.datetime.strptime(json_data['time'], "%Y-%m-%d.%X")

	if (event_type == "heartbeat"):
		vm_uuid = json_data['vm_uuid']
		vm_name = vm_uuid_to_vm_name[vm_uuid]
		vm_vcpus = vm_uuid_to_vcpus[vm_uuid]
		base_perf = SPEC_ISOLATION[vm_name][vm_vcpus]
		output = json_data['output']
		values = re.findall("[0-9]+ seconds;", output)
		values = map(lambda x: int(x.split()[0]), values)
		heartbeat_value = sum(values) / len(values) / float(base_perf)
		if not vm_uuid in per_vm_heartbeats:
			per_vm_heartbeats[vm_uuid] = [ [], [] ]
		per_vm_heartbeats[vm_uuid][0].append(event_time)
		per_vm_heartbeats[vm_uuid][1].append(heartbeat_value)
	elif (event_type == "internal-esd-report"):
		values = json_data['values']
		for vm_uuid in values:
			if not vm_uuid in per_vm_esd_report:
				per_vm_esd_report[vm_uuid] = [ [], [] ]
			per_vm_esd_report[vm_uuid][0].append(event_time)
			per_vm_esd_report[vm_uuid][1].append(values[vm_uuid])
		
	line = fp.readline()

for vm_uuid in per_vm_heartbeats:
	ax = plt.subplot("111")

	x_axis = per_vm_esd_report[vm_uuid][0]
	for i in range(len(per_vm_esd_report[vm_uuid][1][0])):
		y_axis = map(lambda x: x[i], per_vm_esd_report[vm_uuid][1])
		ax.plot(x_axis, y_axis, marker='x')

	x_axis = per_vm_heartbeats[vm_uuid][0]
	y_axis = per_vm_heartbeats[vm_uuid][1]
	ax.plot(x_axis, y_axis, marker='o')

	plt.title(vm_uuid)
	plt.savefig("esd_vs_heartbeat.%s.png" % vm_uuid, bbox_inches = 'tight')
	plt.close()
