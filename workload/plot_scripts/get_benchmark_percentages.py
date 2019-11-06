import sys, json, datetime, random, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

if len(sys.argv) < 2:
	print "usage: %s <executor_output_file>" % sys.argv[0]
	sys.exit(1)

filename = sys.argv[1]
fp = open(filename)
line = fp.readline()
vms_names = dict()
total_vms = 0
gold_vms = 0
while line:
	tokens = line.split(" - ")
	if "Spawned new VM" in line:
		tokens = line.split()
		vm_seq_num = int(tokens[9])
		vm_name = tokens[12]
		vm_name_base = vm_name.split('-')[2] + "-" + vm_name.split('-')[3]
		if not vm_name_base in vms_names:
			vms_names[vm_name_base] = 0
		vms_names[vm_name_base] += 1
		if "gold" in vm_name:
			gold_vms += 1
		total_vms += 1

	line = fp.readline()

print "Total: %d ( %d gold: %d%% )" % (total_vms, gold_vms, float(gold_vms) / total_vms * 100.0)
for b in vms_names:
	print "%s %s %.2f%%" % (b, vms_names[b], float(vms_names[b]) / total_vms * 100.0)
