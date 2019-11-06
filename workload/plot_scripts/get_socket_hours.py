import sys, re, datetime

def str_to_datetime(time_str):
	return datetime.datetime.strptime(time_str, "%Y-%m-%d.%X")

def get_time_diff_seconds(t1, t2):
	return (t1 - t2).total_seconds()

socket_events = { 0: [], 1: [] }
physical_cpus = [ [] for x in range(20) ]
vms_current_pinning = dict()

def pinning_will_open_socket(pinning):
	'''
	Returns a list (bool, bool) to indicate whether each of the two
	sockets will open given the new pinning
	'''
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

def pinning_will_close_socket(vm_uuid, pinning):
	'''
	Returns a list (bool, bool) to indicate whether each of the two
	sockets will close given the new pinning
	'''
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

def add_vm_pinning(vm_uuid, pinning):
	global physical_cpus
	if vm_uuid in vms_current_pinning:
		remove_vm_pinning(vm_uuid)
	for pcpu in pinning:
		physical_cpus[pcpu].append(vm_uuid)
	vms_current_pinning[vm_uuid] = pinning

def remove_vm_pinning(vm_uuid):
	global physical_cpus
	if not vm_uuid in vms_current_pinning:
		print "DELETING A NON EXISTING VM PINNING"
		sys.exit(1)
	current_pinning = vms_current_pinning[vm_uuid]
	for pcpu in current_pinning:
		physical_cpus[pcpu].remove(vm_uuid)
	del vms_current_pinning[vm_uuid]

for filename in sys.argv[1:]:
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
					socket_opens = pinning_will_open_socket(vm_pinning)
					for socket, opened in enumerate(socket_opens):
						if (opened):
							socket_events[socket].append((time, "open"))
					add_vm_pinning(vm_uuid, vm_pinning)
			if deleted_vms:
				for vm_uuid in deleted_vms:
					socket_closes = pinning_will_close_socket(vm_uuid, vms_current_pinning[vm_uuid])
					for socket, closed in enumerate(socket_closes):
						if (closed):
							socket_events[socket].append((time, "closed"))
					remove_vm_pinning(vm_uuid)

		line = fp.readline()

	end_time = time
	fp.close()

for socket in socket_events:
	seconds_open = 0.0
	events = socket_events[socket]
	## If we have odd number of events, the socket never closed :-)
	if len(events) % 2 != 0:
		events.append((end_time, "closed"))
	i = 0
	while i < len(events):
		open_time = events[i][0]
		close_time = events[i+1][0]
		seconds_open += get_time_diff_seconds(close_time, open_time)
		i += 2
	print socket, seconds_open#, socket_events[socket]

total_seconds = get_time_diff_seconds(end_time, start_time)
print "Total:", total_seconds
