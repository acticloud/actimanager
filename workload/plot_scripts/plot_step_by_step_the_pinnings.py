import sys, re, datetime, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def str_to_datetime(time_str):
	return datetime.datetime.strptime(time_str, "%Y-%m-%d.%X")

## Here we hold the current pinning of each VM
vms_current_pinning = dict()

## Chronologically sorted list of the incoming and deleted VMs
new_vms_sorted_list = []
del_vms_sorted_list = []

vm_is_gold = dict()

def add_vm_pinning(vm_uuid, pinning):
	if vm_uuid in vms_current_pinning:
		remove_vm_pinning(vm_uuid)
	vms_current_pinning[vm_uuid] = pinning

def remove_vm_pinning(vm_uuid):
	if not vm_uuid in vms_current_pinning:
		print "DELETING A NON EXISTING VM PINNING"
		sys.exit(1)
	del vms_current_pinning[vm_uuid]

def create_and_save_fig(title, seq_num):
	ax = plt.subplot("111")
	ax.set_ylim(0, 80)
	ax.set_xlim(-1.5, 21.5)
	plt.xticks(np.arange(0, 19.5), np.arange(20))
	plt.yticks([])
	x_axis = range(20)
	bottoms = np.array([ 0 for i in range(20) ])
	for vm_uuid in new_vms_sorted_list:
		y_axis = [ 0 for i in range(20) ]
		if not vm_uuid in del_vms_sorted_list:
			vm_pinning = vms_current_pinning[vm_uuid]
			for pcpu in vm_pinning:
				y_axis[pcpu] = 1
		c = "gold" if vm_is_gold[vm_uuid] else "silver"
		ax.bar(x_axis, y_axis, label=vm_uuid, bottom=bottoms, color=c)
		bottoms += 1
	plt.title(title)
	plt.savefig("boot_times.%03d.png" % seq_num, bbox_inches = 'tight')
	plt.close()

fig_num = 0
filename = sys.argv[1]
fp = open(filename)
line = fp.readline()
while line:
	tokens = line.split(" - ")
	try:
		time = str_to_datetime(tokens[0])
	except: ## Some lines do not have time
		line = fp.readline()
		continue

	if ("===> Execution Loop Starts" in line):
		new_vms = []
		deleted_vms = []
		vm_pinnings = []
		vms_moved = []
	elif ("New VMs:" in line):
		occurrences = re.findall("VM [a-z0-9]{8} :", line)
		new_vms = map(lambda x: x.split()[1], occurrences)
		new_vms_sorted_list += new_vms
		vms_characterization = re.findall("[SG]{1}\|[QN]{1}\|[IS]", line)
		vms_characterization = map(lambda x: x[0], vms_characterization)
		vms_characterization = map(lambda x: True if x == "G" else False, vms_characterization)
		for i, vm_uuid in enumerate(new_vms):
			vm_is_gold[vm_uuid] = vms_characterization[i]
	elif ("Deleted VMs: " in line):
		occurences = re.findall("u'[a-z0-9-]+'", line)
		occurences = map(lambda x: x.replace("u'","").replace("'","")[0:8], occurences)
		deleted_vms = occurences
		del_vms_sorted_list += deleted_vms
	elif ("Moves START:" in line):
		vm_pinnings_current = re.findall("\[[0-9, ]+\]", tokens[3])
		vm_pinnings_current = map(lambda x: x.replace("[","").replace(",","").replace("]","").split(), vm_pinnings_current)
		vm_pinnings_current = map(lambda x: map(int, x), vm_pinnings_current)
		vm_pinnings += vm_pinnings_current
		vms_moved_current = re.findall("<VM [a-z0-9]{8} :", line)
		vms_moved += map(lambda x: x.replace("<VM ", "").replace(" :", ""), vms_moved_current)
	elif ("===> Execution Loop Ends" in line):
		plot_title = ""
		if new_vms:
			for i, vm_uuid in enumerate(vms_moved):
				vm_pinning = vm_pinnings[i]
				add_vm_pinning(vm_uuid, vm_pinning)
			plot_title += "NEW %s" % new_vms
		if deleted_vms:
			for vm_uuid in deleted_vms:
				remove_vm_pinning(vm_uuid)
			has_del_vms = True
			plot_title += " DEL %s" % deleted_vms

		if (plot_title != ""):
			plot_title = time.strftime("%X") + " " + plot_title
			create_and_save_fig(plot_title, fig_num)
			fig_num += 1

	line = fp.readline()

fp.close()
