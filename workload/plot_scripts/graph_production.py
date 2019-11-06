import sys, json, datetime, random, time, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
import numpy as np
import os
from collections import OrderedDict
import csv

sys.path.insert(1, '/home/jim/jimsiak/actimanager')
import Billing

########################################## Configuration ##########################################

paragka = 0.05
home_dir = '/'.join(os.getcwd().split('/')[:4]) + '/'
# Load and save directories
load_dir = home_dir + 'workload/results/plot_inputs/'
save_graph_dir = home_dir + 'workload/results/graphs/'
save_csv_dir = home_dir + 'workload/results/graphs/csv_outputs/'

# For perVM plots
colors = ['black', 'red', 'green', 'blue', 'magenta']
markers = ['s', 'o', '^', 'X', 'x']
sizes = [10,9,8,7,6]

# Tags to replace the scenarios' names for cleaner look
replace = {'vanilla_openstack': 'Openstack', 'gold_socket_isolation': 'Socket', 'gps': 'Socket',
		   'gold_not_oversubscribed': 'GNO', 'gno': "GNO",
		   'actistatic': 'ACTiManager Static', 'actimanager_static': 'ACTiManager Static',
		   'actifull': 'ACTiManager Dynamic'}

silver_m = Billing.silver_money
gold_m = Billing.gold_money

def batch(slowdown):
	return silver_m / slowdown if slowdown < Billing.silver_tolerate else 0.0

def userfacing(gold, slowdown):
	if gold:
		return gold_m if slowdown < Billing.gold_tolerate + paragka else 0.0
	return silver_m if slowdown < Billing.silver_tolerate else 0.0

# Base perfs for benchmarks. Fill in any missing benchmarks
STRESS_CPU_ISOLATION = { 1: {25: 50.13,  50: 100.38, 75: 150.6, 100: 201.96},
						 2: {25: 100.27, 50: 200.35, 75: 301.3, 100: 403.72},
						 4: {25: 200.82, 50: 401.92, 75: 603.5, 100: 807.33},
						 8: {25: 406.11, 50: 803.13, 75: 1206.10, 100:1614.66} }
STRESS_STREAM_ISOLATION = { 1: 10727.72, 2: 9138.285, 4: 8414.2375, 8: 6808.85 }
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

########################################### Parse Files ###########################################

def read_file(filename, vm_output, vm_perfs, vm_event_times, vms_boot_time, gold_vms, vms_hosts, \
			  vms_names, vms_cost_function, vms_vcpus, vm_times_completed, vm_uuid, \
			  est_profit, vm_times_str, vm_esd, vm_esd_reports):
	fp = open(filename)
	excluded = []
	line = fp.readline()
	while line:
		tokens = line.split(" - ")
		if "EVENT" in line:
			try:
				event_data = tokens[2].replace("EVENT: ", "")
				json_data = json.loads(event_data)
				if not 'event' in json_data:
					line = fp.readline()
					continue
				event_type = json_data['event']
				event_str = json_data['time']
				event_time = datetime.datetime.strptime(json_data['time'], "%Y-%m-%d.%X")
				event_epoch = long(event_time.strftime("%s"))

				# Reports
				if event_type == "internal-profit-report":
					hostname = json_data['hostname']
					value = float(json_data['profit-value'])
					if hostname not in est_profit:
						est_profit[hostname] = [value]
					else:
						est_profit[hostname].append(value)
					line = fp.readline()
					continue
				if event_type == "internal-esd-report":
					esd_dict = json_data['values']
					for (vmid, esd_per_vcpu) in esd_dict.items():
						if vmid not in vm_esd:
							vm_esd[vmid] = tuple([[x] for x in esd_per_vcpu])
						else:
							for vcpu in vm_esd[vmid]:
								vcpu.append(esd_per_vcpu[vm_esd[vmid].index(vcpu)])
						if vmid not in vm_esd_reports:
							vm_esd_reports[vmid] = [event_epoch]
						else:
							vm_esd_reports[vmid].append(event_epoch)
					line = fp.readline()
					continue
				if event_type == "acticloud-external-openstack-filter-profit-report":
					line = fp.readline()
					continue

				vm_seq_num = json_data['vm_seq_num']
				if vm_seq_num in excluded:
					line=fp.readline()
					continue
				if event_type == "boot":
					vm_perfs[vm_seq_num] = []
					vm_uuid[vm_seq_num] = json_data['vm_uuid']
					vm_event_times[vm_seq_num] = []
					vm_event_times[vm_seq_num].append(event_epoch)
					vm_times_completed[vm_seq_num] = 0
					vms_boot_time[vm_seq_num] = event_epoch
					vm_times_str[vm_seq_num] = [event_str]
				elif event_type == "shutdown":
					pass
				elif event_type == "spawn":
					vcpus = json_data['vcpus']
					vms_vcpus[vm_seq_num] = vcpus
					vm_output[vm_seq_num] = []
					host = json_data['host']
					vms_hosts[vm_seq_num] = host
				elif event_type == "heartbeat":
					vm_times_completed[vm_seq_num] += 1
					bench = json_data['bench']
					load = 0 if bench != "stress-cpu" else json_data['load']
					output = json_data['output']
					vcpus = json_data['vcpus']
					output_lines = output.split(';')
					perf = 0.0
					base_perf = 1.0
					if "stress-cpu" in bench:
						try:
							perf_line = output_lines[4]
						except:
							if vm_seq_num not in excluded:
								excluded.append(vm_seq_num)
							line = fp.readline()
							continue
						base_perf = STRESS_CPU_ISOLATION[vcpus][load]
						perf = float(perf_line.split()[8])
					elif "stress-stream" in bench:
						first_perf_line_index = 4
						base_perf = STRESS_STREAM_ISOLATION[vcpus]
						perf_sum = 0.0
						for j in range(vcpus):
							try:
								perf_line = output_lines[first_perf_line_index + j]
							except:
								if vm_seq_num not in excluded:
									excluded.append(vm_seq_num)
								break
							if len(perf_line) < 7:
								if vm_seq_num not in excluded:
									excluded.append(vm_seq_num)
								break
							perf = float(perf_line.split()[6])
							perf_sum += perf
						if vm_seq_num in excluded:
							line = fp.readline()
							continue
						perf = perf_sum / vcpus
					elif "spec-" in bench:
						spec_name = bench.split("-")[1]
						base_perf = SPEC_ISOLATION[spec_name][vcpus]
						seconds_sum = 0.0
						seconds_samples = 0
						seconds_list = list()
						for l in output_lines:
							if 'seconds' in l:
								seconds_list.append(int(l.split()[0]))
								seconds_sum += int(l.split()[0])
								seconds_samples += 1
						if seconds_samples == 0:
							if vm_seq_num not in excluded:
								excluded.append(vm_seq_num)
							line = fp.readline()
							continue
						if seconds_sum == 0:
							if vm_seq_num not in excluded:
								excluded.append(vm_seq_num)
							line = fp.readline()
							continue
						vm_output[vm_seq_num].append(tuple(seconds_list))
						perf = (seconds_sum / seconds_samples) / base_perf

					if not "spec-" in bench: ## Spec is fixed above
						perf = perf / base_perf
					if perf == 0:
						if vm_seq_num not in excluded:
							excluded.append(vm_seq_num)
						line = fp.readline()
						continue
					vm_perfs[vm_seq_num].append(perf if perf > 1 else 1.0)
					vm_event_times[vm_seq_num].append(event_epoch)
					vm_times_str[vm_seq_num].append(event_str)

			except ValueError:
				pass
		elif "Spawned new VM" in line:
			tokens = line.split()
			vm_seq_num = int(tokens[9])
			vm_name = tokens[12]
			vms_cost_function[vm_seq_num] = True
			if "gold" in vm_name:
				gold_vms.append(vm_seq_num)
			elif "to_completion" in vm_name:
				vms_cost_function[vm_seq_num] = False
			vms_names[vm_seq_num] = vm_name
		elif "Workload file:" in line:
			workload_file = line.split()[7]

		line = fp.readline()
	dicts = [vms_names, vm_perfs, vm_event_times, vms_boot_time, vms_hosts, vms_cost_function, vms_vcpus, vm_times_completed]
	for vm_seq_num in vms_names:
		try:
			perf_test = vm_perfs[vm_seq_num]
			event_times_test = vm_event_times[vm_seq_num]
			boot_time_test = vms_boot_time[vm_seq_num]
			hosts_test = vms_hosts[vm_seq_num]
			cost_function_test = vms_cost_function[vm_seq_num]
			vcpus_test = vms_vcpus[vm_seq_num]
			times_completed_test = vm_times_completed[vm_seq_num]
		except KeyError:
			excluded.append(vm_seq_num)
	for vm_seq_num in excluded:
		for d in dicts:
			if vm_seq_num in d:
				del d[vm_seq_num]

	if len(excluded):
		return (filename, excluded)
	else:
		return ('0',[])

def parse_files():
	files = [f for f in os.listdir(load_dir) if f.endswith('.txt')]
	if files == []:
		print "No files found with given pattern"
		return None
	files.sort(reverse=True)

	total_measures = OrderedDict() # REALLY large
	failures = []
	for filename in files:
		vm_perfs = dict()
		vm_event_times = dict()
		gold_vms = []
		vms_boot_time = dict()
		vms_hosts = dict()
		vms_names = dict()
		vms_cost_function = dict()
		vms_vcpus = dict()
		vm_times_completed = dict()
		vm_total = dict()
		vm_total_opt = dict()
		vm_mean_perf = dict()
		vm_uuid = dict()
		est_profit = dict()
		vm_output = dict()
		vm_times_str = dict()
		vm_esd = dict()
		vm_esd_reports = dict()
			
		ret = read_file(load_dir + filename, vm_output, vm_perfs, vm_event_times, vms_boot_time, \
						gold_vms, vms_hosts, vms_names, vms_cost_function, vms_vcpus, \
						vm_times_completed, vm_uuid, est_profit, vm_times_str, vm_esd,\
						vm_esd_reports)
		if ret[0] != '0':
			failures.append(ret)
		perf_and_income(vm_perfs, vms_names, vms_cost_function, gold_vms, vm_total, vm_event_times, \
						vms_vcpus, vm_mean_perf, vm_times_completed)
		isolation_income(vms_names, vms_vcpus, vm_total_opt, vm_times_completed)
		dicts = {'vm_perfs': vm_perfs, 'vm_event_times': vm_event_times, 'gold_vms':gold_vms, \
				 'vms_boot_time': vms_boot_time, 'vms_hosts': vms_hosts, 'vms_names': vms_names, \
				 'vms_cost_function': vms_cost_function, 'vms_vcpus': vms_vcpus, \
				 'vm_total': vm_total, 'vm_total_opt': vm_total_opt, 'vm_output': vm_output, \
				 'vm_mean_perf': vm_mean_perf, 'vm_times_completed': vm_times_completed, \
				 'vm_times_str': vm_times_str, 'vm_uuid': vm_uuid, 'vm_esd': vm_esd, \
				 'vm_esd_reports': vm_esd_reports}
		if est_profit:
			dicts['est_profit'] = est_profit
		total_measures[filename] = dicts

	get_socket_hours(total_measures)
	if failures == []:
		print "Parsed all files successfully"
	else:
		for f in failures:
			print "From file: " + f[0] + "\n\tVMs removed: " + str(f[1])
	return total_measures

############################### Mean Perf, Profit, Isolation Profit ###############################

def perf_and_income(vm_perfs, vm_names, vms_cost_function, gold_vms, vm_total, vm_event_times, \
					vms_vcpus, vm_mean_perf, vm_times_completed):
	for vm in vm_names:
		name = vm_names[vm]
		times = vm_times_completed[vm]
		tokens = name.split('-')
		time_axis = vm_event_times[vm]
		if len(time_axis) == 1:
			vm_mean_perf[vm] = 1
			vm_total[vm] = 0
			continue
		if vm_perfs[vm] == []:
			print "EMPTY LIST OF PERFS: ", vm
		vcpus = vms_vcpus[vm]
		duration = time_axis[-1] - time_axis[0]
		duration_mins = duration / 60.0
		if 'to_completion' in tokens:
			spec_name = tokens[3]
			base_time = SPEC_ISOLATION[spec_name][vcpus]
			duration = sum([base_time * x for x in vm_perfs[vm]])
			duration_mins = duration / 60.0
			vm_mean_perf[vm] = min(duration / (base_time * times), np.mean(vm_perfs[vm]))
		else:
			weighted_perfs = []
			for t1 in time_axis[1:]:
				prev_idx = time_axis.index(t1) - 1
				t0 = time_axis[prev_idx]
				dt = t1 - t0
				weighted_perfs.append((t1 - t0) * vm_perfs[vm][prev_idx])
			vm_mean_perf[vm] = sum(weighted_perfs) / duration

		if vms_cost_function[vm]:
			vm_total[vm] = userfacing(vm in gold_vms, vm_mean_perf[vm]) * duration_mins * vcpus
		else:
			vm_total[vm] = batch(vm_mean_perf[vm]) * duration_mins * vcpus
		
def isolation_income(vms_names, vms_vcpus, vm_total_opt, vm_times_completed):
	for vm in vms_names:
		name = vms_names[vm]
		vcpus = vms_vcpus[vm]
		tokens = name.split('-')
		is_gold = tokens[1] == 'gold'
		if 'stress' in tokens:
			time = tokens[6] if 'cpu' in tokens else tokens[5]
			rate = userfacing(is_gold, 1.0)
			vm_total_opt[vm] = rate * int(time) * vcpus
		if 'spec' in tokens:
			spec_name = tokens[3]
			base_time = SPEC_ISOLATION[spec_name][vcpus]
			times = vm_times_completed[vm]
			time = (times * base_time) / 60.0
			rate = userfacing(is_gold, 1.0) if is_gold else batch(1.0)
			vm_total_opt[vm] = rate * time * vcpus

########################################### Socket Hours ##########################################

def str_to_datetime(time_str):
	return datetime.datetime.strptime(time_str, "%Y-%m-%d.%X")

def get_time_diff_seconds(t1, t2):
	return (t1 - t2).total_seconds()

def pinning_will_open_socket(pinning, physical_cpus):
	ret = [False, False]
	for pcpu in pinning:
		socket = 0 if pcpu < 10 else 1
		first_pcpu_to_check = 10 * socket
		last_pcpu_to_check = first_pcpu_to_check + 10
		pcpus_to_check = range(first_pcpu_to_check, last_pcpu_to_check)
		all_pcpus_free = True
		for p in pcpus_to_check:
			if len(physical_cpus[p]) > 0:
				## At least one physical cpu of the current socket is occupied, go to the next pcpu
				all_pcpus_free = False
				break
		if all_pcpus_free:
			ret[socket] = True
	return ret

def pinning_will_close_socket(vm_uuid, pinning, physical_cpus):
	ret = [False, False]
	for pcpu in pinning:
		socket = 0 if pcpu < 10 else 1
		first_pcpu_to_check = 10 * socket
		last_pcpu_to_check = first_pcpu_to_check + 10
		pcpus_to_check = range(first_pcpu_to_check, last_pcpu_to_check)
		one_pcpu_is_occupied = False
		for p in pcpus_to_check:
			if (physical_cpus[p].count(vm_uuid) < len(physical_cpus[p])):
				## At least one physical cpu of the current socket is occupied by other VMs
				one_pcpu_is_occupied = True
				break
		if one_pcpu_is_occupied == False:
			ret[socket] = True
	return ret

def add_vm_pinning(vm_uuid, pinning, vms_current_pinning, physical_cpus):
	if vm_uuid in vms_current_pinning:
		remove_vm_pinning(vm_uuid, vms_current_pinning, physical_cpus)
	for pcpu in pinning:
		physical_cpus[pcpu].append(vm_uuid)
	vms_current_pinning[vm_uuid] = pinning

def remove_vm_pinning(vm_uuid, vms_current_pinning, physical_cpus):
	if not vm_uuid in vms_current_pinning:
		print "DELETING A NON EXISTING VM PINNING"
		sys.exit(1)
	current_pinning = vms_current_pinning[vm_uuid]
	for pcpu in current_pinning:
		physical_cpus[pcpu].remove(vm_uuid)
	del vms_current_pinning[vm_uuid]

def socket_hours_per_file(filename):
	socket_events = { 0: [], 1: [] }
	physical_cpus = [ [] for x in range(20) ]
	vms_current_pinning = dict()
	fp = open(filename)

	line = fp.readline()
	start_time = str_to_datetime(line.split(" - ")[0])
	while line:
		tokens = line.split(" - ")
		try:
			time = str_to_datetime(tokens[0])
		except: ## Some lines do not have time
			line = fp.readline()
			continue

		if ("===> Execution Loop Starts" in line):
			loop_start_time = time
			new_vms = []
			deleted_vms = []
			vm_pinnings = []
			vms_moved = []
		elif ("New VMs:" in line):
			occurrences = re.findall("VM [a-z0-9]{8} :", line)
			new_vms = map(lambda x: x.split()[1], occurrences)
		elif ("Deleted VMs: " in line):
			occurences = re.findall("u'[a-z0-9-]+'", line)
			occurences = map(lambda x: x.replace("u'","").replace("'","")[0:8], occurences)
			deleted_vms = occurences
		elif ("Moves START:" in line):
			vm_pinnings_current = re.findall("\[[0-9, ]+\]", tokens[3])
			vm_pinnings_current = map(lambda x: x.replace("[","").replace(",","").replace("]","").split(), vm_pinnings_current)
			vm_pinnings_current = map(lambda x: map(int, x), vm_pinnings_current)
			vm_pinnings += vm_pinnings_current
			vms_moved_current = re.findall("<VM [a-z0-9]{8} :", line)
			vms_moved += map(lambda x: x.replace("<VM ", "").replace(" :", ""), vms_moved_current)
		elif ("===> Execution Loop Ends" in line):
			loop_end_time = time
			if new_vms:
				for i, vm_uuid in enumerate(vms_moved):
					vm_pinning = vm_pinnings[i]
					socket_opens = pinning_will_open_socket(vm_pinning, physical_cpus)
					for socket, opened in enumerate(socket_opens):
						if (opened):
							socket_events[socket].append((time, "open"))
					add_vm_pinning(vm_uuid, vm_pinning, vms_current_pinning, physical_cpus)
			if deleted_vms:
				for vm_uuid in deleted_vms:
					socket_closes = pinning_will_close_socket(vm_uuid, vms_current_pinning[vm_uuid], physical_cpus)
					for socket, closed in enumerate(socket_closes):
						if (closed):
							socket_events[socket].append((time, "closed"))
					remove_vm_pinning(vm_uuid, vms_current_pinning, physical_cpus)

		line = fp.readline()

	end_time = time
	fp.close()

	answer = list()

	for socket in socket_events:
		seconds_open = 0.0
		events = socket_events[socket]
		if len(events) % 2 != 0:
			events.append((end_time, "closed"))
		i = 0
		while i < len(events):
			open_time = events[i][0]
			close_time = events[i+1][0]
			seconds_open += get_time_diff_seconds(close_time, open_time)
			i += 2
		answer.append(seconds_open)

	total_seconds = get_time_diff_seconds(end_time, start_time)
	return sum(answer) / (len(answer) * total_seconds)

def get_socket_hours(measures):
	results_dir = '/'.join(load_dir.split('/')[:6] + [''])
	for filename in measures:
		if filename.startswith('0.vanilla_openstack'):
			measures[filename]['socket_hours'] = 1.0
			continue
		socket_hours = 0
		files = []
		cfg = max([x for x in filename.split('.') if 'vcpus' in x])
		ending = '.'.join(filename.split('.')[(filename.split('.').index(cfg) + 1):])
		for i in range(1,5):
			files.append(filename.split('rate')[0] + 'rate.' + 'internal-acticloud' + str(i) + '.' + ending)
		for f in files:
			try:
				fp = open(results_dir + f)
				fp.close()
			except:
				print "Did not find:", f
				continue

			socket_hours += socket_hours_per_file(results_dir + f)
		measures[filename]['socket_hours'] = socket_hours / len(files)

########################################### CSV Writers ###########################################

def csv_writer(total_measures):
	load_mix = sorted(list(set([x.split('-')[-2] for x in total_measures.keys()])), \
					  key = lambda x: int(x.split('_')[0]))
	noisy_mix = sorted(list(set([x.split('-')[-3] for x in total_measures.keys()])), \
					   key = lambda x: int(x.split('_')[0]))
	gold_mix = sorted(list(set([x.split('-')[-4] for x in total_measures.keys()])), \
					  key = lambda x: int(x.split('_')[0]))
	variable = max([load_mix, noisy_mix, gold_mix], key = lambda x: len(x))
	scenarios = sorted(list(set([x.split('-')[0].split('.')[-1] for x in total_measures.keys()])), \
					   reverse = True)
	for load in variable:
		files = [f for f in total_measures.keys() if load in f.split('-')]
		out_file = save_csv_dir + load.split('_')[-1] + '/' + load + '.csv'
		with open(out_file, mode='w') as fd:
			writer = csv.writer(fd, delimiter='\t')
			overtitle = ['Characteristics','','','']
			titles = ['VM', 'Name', 'vCPUs', 'Is Gold']
			for f in files[::-1]:
				name_ = f.split('.')[1].split('-')[0]
				label = replace[name_] if name_ in replace else name_ + ' ' + f.split('.')[-2]
				overtitle += [label, '','','','','']
				titles += ['Boot', 'Dur.', 'Times', 'Inc.', 'SlD', 'Max']
			writer.writerow(overtitle)
			writer.writerow(titles)
				
			vm_count = max([len(total_measures[filename]['vms_names'].keys()) for filename in files])
			ref_file = [f for f in files if len(total_measures[f]['vms_names'].keys()) == vm_count][0]
			names = total_measures[ref_file]['vms_names']
			vcpus = total_measures[ref_file]['vms_vcpus']
			gold_vms = total_measures[ref_file]['gold_vms']

			base_times = dict()
			for f in files:
				base_times[f] = total_measures[f]['vms_boot_time'][0]

			for vm in range(vm_count):
				_name = '-'.join(names[vm].split('-')[3:4])
				_vcpus = vcpus[vm]
				_gold = str(vm in gold_vms).upper()

				line = [vm, _name, _vcpus, _gold]
				
				for filename in files[::-1]:
					if vm in total_measures[filename]['vms_names']:
						_boot = total_measures[filename]['vms_boot_time'][vm] - base_times[filename]
						_dur = "{0:.2}".format((total_measures[filename]['vm_event_times'][vm][-1] - total_measures[filename]['vm_event_times'][vm][0]) / 60.0)
						_times = total_measures[filename]['vm_times_completed'][vm]
						_money = int(total_measures[filename]['vm_total'][vm])
						_sd = "{0:.3}".format(float(total_measures[filename]['vm_mean_perf'][vm]))
						_opt = int(total_measures[filename]['vm_total_opt'][vm])
						line += [_boot, _dur, _times, _money, _sd, _opt]
					else:
						line += ["", "", "", "", "", ""]
				writer.writerow(line)
			fd.close()

def income_per_scenario(total_measures):
	load_mix = sorted(list(set([x.split('-')[-2] for x in total_measures.keys()])), \
					  key = lambda x: int(x.split('_')[0]))
	noisy_mix = sorted(list(set([x.split('-')[-3] for x in total_measures.keys()])), \
					   key = lambda x: int(x.split('_')[0]))
	gold_mix = sorted(list(set([x.split('-')[-4] for x in total_measures.keys()])), \
					  key = lambda x: int(x.split('_')[0]))
	variable = max([load_mix, noisy_mix, gold_mix], key = lambda x: len(x))
	scenarios = sorted(list(set([x.split('-')[0].split('.')[-1] for x in total_measures.keys()])), \
					   reverse = True)

	out_file = save_csv_dir + "income-per-scenario" + '.csv'
	with open(out_file, mode='w') as fd:
		writer = csv.writer(fd, delimiter='\t')
		title = ["Util.", "Scenario", "Gold Income", "Silver Income", "Total Income", \
				 "Max Income", "Gold Paid", "Silver Paid", "Total Paid", "VMs (Gold, Silver)"]
		ans = ""
		writer.writerow(title)
		for u in variable:
			ans += u.split('-')[-1].split('_')[0]
			line = []
			for (i, s) in enumerate(scenarios):
				line.append('' if i else u.split('_')[0])
				scen = replace[s] if s in replace else s
				files = [x for x in total_measures if s in x and '-' + u in x]
				for f in files:
					vm_total = total_measures[f]['vm_total']
					gold_vms = total_measures[f]['gold_vms']
					socket_hours = total_measures[f]['socket_hours']
					vm_total_opt = total_measures[f]['vm_total_opt']
					gold_income = sum([vm_total[x] for x in vm_total if x in gold_vms])
					gold_paid = sum(map(lambda x: int(bool(x)), [vm_total[i] for i in vm_total if i in gold_vms]))
					if '1.gps' in f:
						gold_income = sum([vm_total_opt[x] for x in vm_total_opt if x in gold_vms])
						gold_paid = sum(map(lambda x: int(bool(x)), [vm_total_opt[i] for i in vm_total_opt if i in gold_vms]))
					silver_income = sum([vm_total[x] for x in vm_total if x not in gold_vms])
					total = gold_income + silver_income
					isolation = sum(vm_total_opt.values())
					gold_all = len(gold_vms)
					total_paid = sum(map(lambda x: int(bool(x)), vm_total.values()))
					total_all = len(vm_total.keys())
					line += [scen, int(round(gold_income)), int(round(silver_income)), \
							 int(round(total)), int(round(isolation)), gold_paid, \
							 total_paid - gold_paid, total_paid, \
							 str(gold_all) + ", " + str(total_all - gold_all)]
					writer.writerow(line)
					ans += "\t" + scen + ' ' + f.split('.')[-2] +"\t" + str(int(round(gold_income))) + "\t" + \
							str(int(round(silver_income))) + "\t" + str(int(round(total))) + "\t" + \
							str(int(round(isolation))) + "\t" + str(gold_paid) + "/" + str(gold_all) + "\t" + \
							str(total_paid - gold_paid) + "/" + str(total_all - gold_all) + "\t" + \
							"{0:.1f}".format(socket_hours * 100) + "%" +"\n"
		fd.close()
		print ans

def print_vcpus_sd(total_measures):
	load_mix = sorted(list(set([x.split('-')[-2] for x in total_measures.keys()])), \
					  key = lambda x: int(x.split('_')[0]))
	noisy_mix = sorted(list(set([x.split('-')[-3] for x in total_measures.keys()])), \
					   key = lambda x: int(x.split('_')[0]))
	gold_mix = sorted(list(set([x.split('-')[-4] for x in total_measures.keys()])), \
					  key = lambda x: int(x.split('_')[0]))
	variable = max([load_mix, noisy_mix, gold_mix], key = lambda x: len(x))
	scenarios = sorted(list(set([x.split('-')[0].split('.')[-1] for x in total_measures.keys()])), \
					   reverse = True)

	out_file = save_csv_dir + "vcpus-sd" + '.csv'
	with open(out_file, mode='w') as fd:
		writer = csv.writer(fd, delimiter='\t')
		for util in variable:
			print util.split('-')[-1].split('_')[0]
			line = [util.split('_')[0]]
			for scenario in scenarios:
				files = [x for x in total_measures if scenario in x and '-' + util in x]
				for filename in files:
					gold_vms = total_measures[filename]['gold_vms']
					(gold_vcpus, silver_vcpus, gold_sd, silver_sd) = (0, 0, 0, 0)
					for vm in total_measures[filename]['vms_names']:
						if vm in gold_vms:
							gold_vcpus += total_measures[filename]['vms_vcpus'][vm]
							gold_sd += total_measures[filename]['vm_mean_perf'][vm]
						else:
							silver_vcpus += total_measures[filename]['vms_vcpus'][vm]
							silver_sd += total_measures[filename]['vm_mean_perf'][vm]
					if len(gold_vms):
						gold_sd /= len(gold_vms)
					else:
						gold_sd = 0.0
					if (len(total_measures[filename]['vms_names'].keys()) - len(gold_vms)):
						silver_sd /= (len(total_measures[filename]['vms_names'].keys()) - len(gold_vms)) 
					else:
						silver_sd = 0.0
					hw_util = total_measures[filename]['socket_hours']
					
					line += [(replace[scenario] if scenario in replace else scenario), \
							 gold_vcpus, silver_vcpus, "{0:.2f}".format(gold_sd), \
							 "{0:.2f}".format(silver_sd), hw_util]
					print "\t" + (replace[scenario] if scenario in replace else scenario) + " " + \
						  filename.split('.')[-2] + "\t" + \
						  str(gold_vcpus) + "\t" + str(silver_vcpus) + "\t" + \
						  "{0:.2f}".format(gold_sd) + "\t" + \
						  "{0:.2f}".format(silver_sd) + "\t" + str(hw_util)
				writer.writerow([''])
			print "\n"
		fd.close()

########################################### VM Details ############################################

def print_esd(vm, measures):
	print "------------------------------- ESD --------------------------------" 
	uuid = measures['vm_uuid'][vm]
	vm_esd = measures['vm_esd'][uuid]
	vm_perfs = measures['vm_perfs'][vm]
	vm_esd_reports = measures['vm_esd_reports'][uuid]
	vm_event_times = measures['vm_event_times'][vm]
	events = []
	for t1 in vm_event_times:
		for r in vm_esd_reports:
				if r > t1:
					events.append(vm_esd_reports.index(r))
					break
	mean_esd = []
	for i in range(len(events) - 1):
		mean_esd.append(tuple([np.mean(vcpu[events[i]:events[i+1]]) for vcpu in vm_esd]))
	for i in range(len(vm_perfs)):
		print "Execution:", i, "\tPerf:", "{0:.2f}".format(vm_perfs[i]), "|", "ESD:", \
			  ', '.join(["{0:.2f}".format(x) for x in mean_esd[i]])
	print "____________________________________________________________________"

def print_details_of_vm(vm, measures):
	print "------------------------ VM Characteristics ------------------------" 
	spec_name = measures['vms_names'][vm].split('-')[3]
	vcpus = measures['vms_vcpus'][vm]
	base = SPEC_ISOLATION[spec_name][vcpus]
	print "\t\tVM Sequence Number: " + str(vm)
	print "VM Name:", measures['vms_names'][vm]
	print "   uuid: ", measures['vm_uuid'][vm]
	print "Base perf:", base, "Cost Function:", "UserFacing" if measures['vms_cost_function'][vm] else "Batch", "vCPUs:", vcpus
	print "Times Completed:", measures['vm_times_completed'][vm]
	print "Output:", measures['vm_output'][vm]
	print "Mean Perf", float("{0:.2f}".format(measures['vm_mean_perf'][vm]))
	tolerate = Billing.gold_tolerate if vm in measures['gold_vms'] else Billing.silver_tolerate
	failed_executions = [(i, float("{0:.2f}".format(x))) for (i,x) in enumerate(measures['vm_perfs'][vm]) if x > tolerate]
	if failed_executions:
		print "\nFailed Executions:\n", failed_executions
		print "Which Started at:"
		print [x for (i,x) in enumerate(measures['vm_times_str'][vm][:-1]) if measures['vm_perfs'][vm][i] > tolerate] 
	print "\nHost:", measures['vms_hosts'][vm]
	print "Income:", measures['vm_total'][vm]
	print "Income in Isolation:", measures['vm_total_opt'][vm]

def print_details(total_measures):
	fn = None
	if len(total_measures.keys()) == 1:
		fn = total_measures.keys()[0]
	else:
		print "Choose a file: (index or filename)"
		for (i, filename) in enumerate(total_measures.keys()):
			print "\t" + str(i) + ". " + filename.split('/')[-1]
		fn = raw_input("> ")
	if len(fn) > 3:
		filename = fn
	else:
		filename = total_measures.keys()[int(fn)]
	measures = total_measures[filename]
	while True:
		vms_to_print = raw_input("Which VM? > ")
		if not vms_to_print:
			return
		print_vms = []
		if vms_to_print == "missed":
			print_vms = [vm for vm in measures['gold_vms'] if measures['vm_total'][vm] == 0]
		elif vms_to_print == "gold":
			print_vms = [vm for vm in measures['gold_vms']]
		elif vms_to_print == "all":
			print_vms = [vm for vm in measures['vms_names']]
		else:
			try:
				vm_seq_num = int(vms_to_print)
				name = measures['vms_names'][vm_seq_num]
			except:
				assert False, "Invalid Sequence Number " + vms_to_print
			print_vms = [vm_seq_num]	
		for vm in print_vms:
			print_details_of_vm(vm, measures)
			if "acti" in filename:
				print_esd(vm, measures)
			if len(print_vms) > 1 and print_vms.index(vm) < len(print_vms) - 1:
				next_ = raw_input("")
				if next_ == "q":
					return

############################################## Main ###############################################

def main(graph = 'all'):
	total_measures = parse_files()
	if graph == 'esd':
		print_esd(total_measures)
	if graph == 'bar' or graph == 'all':
		income_per_scenario(total_measures)
		print_vcpus_sd(total_measures)
	if graph == 'csv' or graph == 'all':
		csv_writer(total_measures)
	if graph == 'detail':
		print_details(total_measures)
	if graph == 'help':
		print "Usage: python graph_production $GRAPH"
		print "$GRAPH can be:"
		print "\tpervm\t: prints the profit and slowdown per vm"
		print "\tbar\t: prints a bar plot and an Excel compatible output"
		print "\tcsv\t: generates a csv file containing detailed information"
		print "\tprofit\t: plots the estimated profit"
		print "\tdetail\t: prints details on VMs"

try:
	graph = sys.argv[1]
except:
	graph = 'all'
main(graph)

############################################# Graphs ##############################################
#
#def per_vm_plots(total_measures):
#	for util in list(set([x.split('/')[-1].split('-')[-2].split('_')[0] for x in total_measures.keys()])):
#		print "Utilization: " + util
#
#		measures = OrderedDict()
#		for f in total_measures:
#			if util in f:
#				measures[f] = total_measures[f]
#
#		for goldplot in range(2):
#			print "\tPlotting for " + ("GOLD" if goldplot else "SILVER") + " VMs"
#			for plot_money in range(2):
#				idx = 0
#				print "\t\tPlotting for " + ("Profit" if plot_money else "Slowdown") 
#				ax = plt.subplot("111")
#				title = "Util: " + util + "%" + (" Gold " if goldplot else " Silver ") + "VMs "
#				vms_count = list()
#				for filename in measures.keys()[::-1]:
#					label = filename.split('/')[-1].split('-')[0].split('.')[-1]
#					y_axis = measures[filename]['vm_total' if plot_money else 'vm_mean_perf']
#					gold_vms = measures[filename]['gold_vms']
#					plot_cfg = (colors[idx], markers[idx], sizes[idx])
#					plotme(ax, plot_cfg, label, util, y_axis, gold_vms, bool(goldplot))
#					all_vms = len(measures[filename]['vm_perfs'].keys())
#					num_gold = len(measures[filename]['gold_vms'])
#					vms_count.append(all_vms)
#					title += " | " + label + " " + str(num_gold if goldplot else all_vms - num_gold)
#					title += " / " + str(all_vms)
#					idx += 1
#
#				if not plot_money:
#					ax.plot(range(max(vms_count)), [Billing.gold_tolerate if goldplot else Billing.silver_tolerate] * max(vms_count))
#				ax.legend(bbox_to_anchor=(1, 1), bbox_transform=plt.gcf().transFigure)
#				fig = matplotlib.pyplot.gcf()
#				fig.set_size_inches(18.5, 10.5)
#				plt.xticks(np.arange(0, max(vms_count), 2.0), rotation=90)
#				plt.title(title, size='x-large')
#				plt.xlabel('VMs', size='large')
#				plt.ylabel('profit' if plot_money else 'Slowdown', rotation=90, size='large')
#				fig = matplotlib.pyplot.gcf()
#				plt.grid(which='both', axis='x', color='grey')
#				plt.grid(which='major', axis='y', color='grey')
#				plt.savefig(save_graph_dir + util + "_" + ('gold' if goldplot else 'silver') + ("_profit.png" if plot_money else "_slowdown.png"))
#				plt.close()
#		print "End of Util.: " + util
#		print "-----------------------------------------------"
#
#def plotme(ax, plot_cfg, label, util, plot_dict, gold_vms, is_gold):
#	(color, marker, size) = plot_cfg
#	if is_gold:
#		x_axis = sorted([x for x in plot_dict.keys() if x in gold_vms])
#	else:
#		x_axis = sorted([x for x in plot_dict.keys() if x not in gold_vms])
#	y_axis = []
#	for vm in x_axis:
#		#if vm_total[vm] < 40 and vm_total[vm] > 0.5:
#		y_axis.append(plot_dict[vm])
#		#else:
#		#	y_axis.append(2)
#
#	if marker == 's':
#		ax.plot(x_axis,y_axis, mec=color, marker=marker, mfc = 'None', mew = 3, label=label, \
#				markersize=size, linewidth=0)
#	else:
#		ax.plot(x_axis,y_axis, color=color, marker=marker, label=label, markersize=size, linewidth=0)
#
