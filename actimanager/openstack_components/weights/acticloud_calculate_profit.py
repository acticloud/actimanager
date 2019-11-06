from oslo_log import log as logging
import numpy as np

LOG = logging.getLogger(__name__)

## FIXME: these should be moved to a configuration file
GOLD_VM_PAYING_THRESHOLD = 1.2
SILVER_VM_PAYING_THRESHOLD = 4.0
GOLD_VM_BASE_RATE = 10.0
SILVER_VM_BASE_RATE = 1.0
SERVER_COST = 20.0
SILVER_OVERSUBSCRIPTION_RATIO = 4.0

INTERFERENCE_MATRIX = [ [ 1.01, 1.03 ], [ 1.03, 1.06 ] ]

def calculate_vm_esd(vm, _nr_total_vcpus, _nr_gold_vcpus, nr_host_vcpus):
	vm_vcpus = int(vm['nr_vcpus'])
	vm_is_gold = int(vm['is_gold'])
	vm_is_noisy = int(vm['is_noisy'])
	vm_is_sensitive = int(vm['is_sensitive'])

	interference_matrix = INTERFERENCE_MATRIX
	nr_total_vcpus = np.array(_nr_total_vcpus)
	nr_gold_vcpus = np.array(_nr_gold_vcpus)

	## Take out of the arrays the current vm
	nr_total_vcpus[0] -= vm_vcpus
	nr_total_vcpus[1] -= vm_vcpus * vm_is_noisy
	nr_total_vcpus[2] -= vm_vcpus * vm_is_sensitive
	nr_gold_vcpus[0] -= vm_vcpus * vm_is_gold
	nr_gold_vcpus[1] -= vm_vcpus * vm_is_gold * vm_is_noisy
	nr_gold_vcpus[2] -= vm_vcpus * vm_is_gold * vm_is_sensitive
	nr_silver_vcpus = nr_total_vcpus - nr_gold_vcpus

	col_ind = vm_is_sensitive

	## Calculate the interference from gold VMs, the easy part
	nr_gold_noisy_vcpus = nr_gold_vcpus[1]
	nr_gold_quiet_vcpus = nr_gold_vcpus[0] - nr_gold_noisy_vcpus
	interferences_sum = sum([interference_matrix[0][col_ind]] * nr_gold_quiet_vcpus +
	                        [interference_matrix[1][col_ind]] * nr_gold_noisy_vcpus)
	interferences_avg = interferences_sum / (nr_gold_vcpus[0] or 1)
	## NOTE(jimsiak): If (nr_gold_vcpus[0] / 2.0) is ceil() actimanager external
	## becomes more pessimistic
	interference_from_gold = interferences_avg ** (nr_gold_vcpus[0] / 2.0)

	## Calculate the interference from silver VMs, welcome to hell!
	nr_silver_total_vcpus = nr_silver_vcpus[0]
	nr_silver_noisy_vcpus = nr_silver_vcpus[1]
	nr_silver_quiet_vcpus = nr_silver_total_vcpus - nr_silver_noisy_vcpus
	### How many host vcpus are occupied by silver VMs?
	nr_host_vcpus_silver = nr_host_vcpus - nr_gold_vcpus[0]
	## If the number of silver vcpus is less than the total number of vcpus available
	## silver vcpus occupy less total vcpus
	if nr_silver_total_vcpus < nr_host_vcpus_silver:
		nr_host_vcpus_silver = nr_silver_total_vcpus
	### What is the oversubscription ratio?
	if nr_silver_total_vcpus == 0 or nr_silver_total_vcpus == nr_host_vcpus_silver:
		oversubscription_ratio = 1.0
	else:
		oversubscription_ratio = float(nr_silver_total_vcpus) / nr_host_vcpus_silver
	### Get the average of interferences
	interferences_sum = sum([interference_matrix[0][col_ind]] * nr_silver_quiet_vcpus +
	                        [interference_matrix[1][col_ind]] * nr_silver_noisy_vcpus)
	interferences_avg = interferences_sum / (nr_silver_total_vcpus or 1)
	interference_from_silver = interferences_avg ** (nr_host_vcpus_silver / 2.0)

	interference_osb = 1.0 if vm_is_gold else oversubscription_ratio 

	return interference_osb * interference_from_gold * interference_from_silver

def calculate_host_profit(vms, nr_vcpus_host):
	## Setup the nr_{total, gold, silver}_vcpus arrays
	nr_total_vcpus = np.array([0, 0, 0]) # [ total, noisy, sensitive ]
	nr_gold_vcpus  = np.array([0, 0, 0]) # [ total, noisy, sensitive ]
	for vm in vms:
		vm_vcpus = int(vm['nr_vcpus'])
		vm_is_gold = int(vm['is_gold'])
		vm_is_noisy = int(vm['is_noisy'])
		vm_is_sensitive = int(vm['is_sensitive'])
		nr_total_vcpus[0] += vm_vcpus
		nr_total_vcpus[1] += vm_vcpus * vm_is_noisy
		nr_total_vcpus[2] += vm_vcpus * vm_is_sensitive
		nr_gold_vcpus[0] += vm_vcpus * vm_is_gold
		nr_gold_vcpus[1] += vm_vcpus * vm_is_gold * vm_is_noisy
		nr_gold_vcpus[2] += vm_vcpus * vm_is_gold * vm_is_sensitive
	nr_silver_vcpus = nr_total_vcpus - nr_gold_vcpus

	## Calculate the host's profit
	esds = []
	host_profit = 0.0
	for vm in vms:
		vm_is_gold = int(vm['is_gold'])
		esd = calculate_vm_esd(vm, nr_total_vcpus, nr_gold_vcpus, nr_vcpus_host)
#		esd = 0.95 * esd ## Make external a bit more optimistic :-D
		esds.append(esd)

		paying_threshold = GOLD_VM_PAYING_THRESHOLD \
		                   if vm_is_gold \
		                   else SILVER_VM_PAYING_THRESHOLD
		base_rate = GOLD_VM_BASE_RATE if vm_is_gold else SILVER_VM_BASE_RATE
		profit_per_vcpu = base_rate if esd < paying_threshold else 0.0
		profit_per_vm = profit_per_vcpu * int(vm['nr_vcpus'])
		host_profit += profit_per_vm

	LOG.info("Calculated ESDs for VMs: %s", esds)
	return host_profit

if __name__ == '__main__':
	G = 1; S = 0; N = 1; Q = 0; Se = 1; I = 0
	vms = list()
	acti1 = [(8, S, N, Se), (1, G, N, I), (4, S, N, Se)]
	acti2 = [(1,S,N,I),(2,S,Q,I),(1,S,Q,I),(4,G,N,Se),(2,S,Q,I),(2,S,Q,I),(2,S,Q,I),(1,S,Q,S)]
	acti3 = [(1,G,N,S),(2,S,Q,I),(1,S,Q,I),(2,S,N,S),(1,S,Q,I),(2,S,N,S)]

	test = [(2,G,N,Se), (4,G,Q,Se), (4,S,N,Se), (1,G,N,S)]

	to_put = test
#	to_put.append((1,S,N,Se))
	for i, vm in enumerate(to_put):
		vms.append({'id': i, 'nr_vcpus': vm[0], 'is_gold': vm[1], 'is_noisy': vm[2],
		            'is_sensitive': vm[3]})

	print calculate_host_profit(vms, 20)
