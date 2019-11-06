import sys, logging, os, commands, threading
import HealthyStateModel

sys.path.append('../common/')
sys.path.append('../actidb/')
from acticloudDB import ActiCloudDBClient
from openstack_client import OpenstackClient

perf_interval = 500 # millisec
perf_window = 25    # seconds
perf_events = "branches,branch-misses,cycles,instructions,context-switches," + \
              "cpu-migrations,page-faults,LLC-loads,LLC-load-misses,dTLB-loads," + \
              "dTLB-load-misses,mem-loads,mem-stores"
perf_outputs_dir = "../actimanager/perf_outputs"

class InterferenceDetector():
	def __init__(self, hostname):
		self.logger = logging.getLogger(self.__class__.__name__)
		self.hostname = hostname

		## Initialize the acticloudDB client
		self.acticloudDB_client = ActiCloudDBClient()

		## Openstack client to get the necessary information when needed
		self.openstack_client = OpenstackClient()

		## VMs that are being monitored, indexed by uuid
		self.monitored_vms = dict()

		## Spawned perf threads
		self.perf_threads = []

	# vm: openstack VM object
	def check_interference(self, vm):
		## Find (if exists) the model of the current benchmark
		model = self._get_model(vm)

		## If no model exists in our database, we don't know about interference
		if (model == None):
			return False
		
		## If the model was found we know ...
		inp_file = self._get_perf_output_filename(vm)
		if (not os.path.isfile(inp_file)):
			self.logger.error("Could not find a current perf output file for VM %s", vm.id)
			return False

		## Everything is in place, checkout about interference
		(num_of_clusters, train_axis, train_labels,
		 model, dev, train_metr, pca, scaler1, scaler2) = model
		has_interference = HealthyStateModel.model_test_dy(train_axis, inp_file, \
						num_of_clusters, train_labels, model, dev, train_metr, \
						pca, scaler1, scaler2)
		return has_interference

	# vm: openstack VM object
	def add_vm(self, vm):
		if vm in self.monitored_vms:
			self.logger.info("VM %s is already being monitored", vm.id)
			return

		self.logger.info("Adding VM %s", vm.id)
		self.monitored_vms[vm] = dict()

	# vm: openstack VM object
	def remove_vm(self, vm):
		if not vm in self.monitored_vms:
			self.logger.info("VM %s is not being monitored", vm.id)
			return

		self.logger.info("Removing VM %s", vm.id)
		del self.monitored_vms[vm]

	def remove_vm_by_uuid(self, vm_uuid):
		for vm in self.monitored_vms:
			if vm_uuid == vm.id:
				self.remove_vm(vm)
				return
		self.logger.info("VM with UUID=%s not found in monitored VMs", vm_uuid)

	def remove_all_vms(self):
		self.monitored_vms = dict()

	## Spawns a perf_thread per monitored VM
	def start_perf_threads(self):
		for vm in self.monitored_vms:
			vm_uuid = vm.id
			vm_pid = self._get_pid_from_vm_id(vm)
			if vm_pid == -1:
				self.logger.info("Could not get the PID of VM %s", vm_uuid)
				continue

			t = threading.Thread(target=self._perf_thread_function, args=(vm, vm_uuid, vm_pid,))
			t.start()
			self.perf_threads.append(t)

	def stop_perf_threads(self):
		for t in self.perf_threads:
			t.join()

	# vm: openstack VM object
	def _get_model(self, vm):
		vm_name = vm.name
		tokens = vm_name.split("-")
		if (len(tokens) < 4):
			model = None ## Could not get benchmark name, no model available
		else:
			bench_name = tokens[2] + "-" + tokens[3] ## FIXME this is not correct for stress
			nr_vcpus = int(self.openstack_client.get_flavor_by_id(vm.flavor["id"]).vcpus)
			model = self.acticloudDB_client.get_model(bench_name, nr_vcpus)
		if model == None:
			self.logger.info("Healthy state model NOT FOUND for VM %s", vm.id)
		else:
			self.logger.info("Healthy state model FOUND for VM %s (db entry: %s, %d)",
			                 vm.id, bench_name, nr_vcpus)
		return model
				
	def _get_perf_output_filename(self, vm):
		return perf_outputs_dir + "/" + vm.id + ".perf"
		## FIXME the following are temporary
#		tokens = vm.name.split("-")
#		bench_name = tokens[2]
#		if "spec" in bench_name:
#			bench_name = bench_name + "-" + tokens[3]
#		nr_vcpus = int(openstack_client.get_flavor_by_id(vm.flavor["id"]).vcpus)
#		return perf_outputs_dir + "/" + bench_name + "-" + str(nr_vcpus) + "vcpus.perf"
		

	def _write_perf_output_to_file(self, vm, vm_uuid, output):
		output_file = self._get_perf_output_filename(vm)
		f = open(output_file, "w")
		f.write(output)
		f.close()

	def _perf_thread_function(self, vm, vm_uuid, vm_pid):
		self.logger.info("Starting perf command for VM %s", vm_uuid)
		perf_cmd = ("ssh %(hostname)s perf kvm --guest stat -e %(events)s " + \
		           "-I %(interval)s -p %(pid)d sleep %(runtime)d") % \
		           {'hostname': self.hostname, 'events': perf_events,
		            'interval': perf_interval, 'pid': vm_pid,
		            'runtime': perf_window}
		self.logger.info("Running perf command for VM %s (PID: %d)", vm.id, vm_pid)
		status, output = commands.getstatusoutput(perf_cmd)
		if status != 0:
			self.logger.info("Something went wrong with the perf command: %s", output)
			return

		self.monitored_vms[vm]['last_perf_output'] = output

		self._write_perf_output_to_file(vm, vm_uuid, output)

	## vm: openstack VM object
	## returns pid: int, on error -1 is returned
	def _get_pid_from_vm_id(self, vm):
		try:
			libvirt_instance_name = getattr(vm, 'OS-EXT-SRV-ATTR:instance_name')
			command = "ssh %s ps -ef | grep %s | grep \"qemu-system\" | grep -v grep | awk '{print $2}'" % (self.hostname, libvirt_instance_name)
			pid = commands.getoutput(command)
			return int(pid)
		except:
			return -1

## The following is here for debugging reasons
if __name__ == '__main__':
	import sys, time


	## Setup the logging facility
	logging.basicConfig(stream=sys.stdout, level=logging.INFO,
	                    format='%(asctime)s - %(name)20s - %(message)s',
	                    datefmt='%Y-%m-%d.%H:%M:%S')
	logging.Formatter.converter = time.gmtime
	logger = logging.getLogger("interference-detector")

	## Check and then read arguments
	if (len(sys.argv) < 2):
		logger.error("usage: %s <hostname>", sys.argv[0])
		sys.exit(1)
	hostname = sys.argv[1]

	## Initialize openstack client
	openstack_client = OpenstackClient()
	
	## Initialize Interference Detector
	detector = InterferenceDetector(hostname)

	while 1:
		## Delete all previously monitored VMs
		detector.remove_all_vms()

		## Add all the VMs to be monitored
		for vm in openstack_client.get_vms_by_hostname(hostname):
			if "acticloud" in vm.name:
				detector.add_vm(vm)

		## Start and wait for perf threads to finish
		detector.start_perf_threads()
		detector.stop_perf_threads()

		for vm in openstack_client.get_vms_by_hostname(hostname):
			if "acticloud" in vm.name:
				has_interference = detector.check_interference(vm, vm.id)
				print "%s INTERFERENCE: %s" % (vm.name, has_interference)
