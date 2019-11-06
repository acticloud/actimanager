import logging
log = logging.getLogger(__name__)

import time
import glob, os, sys, socket
import pytz
from datetime import datetime
import credentials

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
from novaclient import client as novaclient
from gnocchiclient.v1 import client as gnocchiclient

import configparser
config = configparser.ConfigParser()
config.read("actimanager.cfg")
CFG_SECTION = "characterization_agent"

class ActiCloudCharacterizationAgent():
	def __init__(self, lab_compute_node):
		self.LAB_COMPUTE_NODE = lab_compute_node
		self.POLLING_PERIOD = config.getint(CFG_SECTION, "polling_period")
		log.info("Starting characterization agent for node %(c)s with %(s)s seconds interval",
		         {'c': self.LAB_COMPUTE_NODE, 's': self.POLLING_PERIOD})

		creds = credentials.get_nova_creds()
		self.nova = novaclient.Client("2", **creds)

		auth = v3.Password(**creds)
		sess = session.Session(auth=auth)
		self.gnocchi = gnocchiclient.Client(sess)

	def getServerListByComputeNode(self, computeNode):
		return self.nova.servers.list(search_opts={'host': computeNode})

	def get_vm_qemu_vcpu_pid(self, vm):
		try:
			libvirt_name = getattr(vm, 'OS-EXT-SRV-ATTR:instance_name')
			path = "/sys/fs/cgroup/cpuset/machine/qemu-*-" + libvirt_name + ".libvirt-qemu/vcpu0/tasks"
			for filename in glob.glob(path):
				with open(filename, 'r') as f:
					pid = f.readline().split()[0]
					return pid
		except:
			return -1

	def extract_measures(self, events):
		'''
		Parses 'output.txt' file and returns a dictionary
		'''
		log.info("Collecting data [ events: %(e)s ]...", {'e': events})
		fp = open("output.txt", "r")

		values = dict()
		for event in events.split(','):
			values[event] = 0.0

		measure_ipc = False
		if 'cycles' in values and 'instructions' in values:
			measure_ipc = True
			values['ipc_mean'] = 0.0
			values['ipc_var'] = 0.0

		line = fp.readline()
		while line:
			tokens = line.split()
			if line.startswith("#") or len(tokens) < 3:
				line = fp.readline()
				continue
			event = tokens[2]
			value = float(tokens[1].replace(',',''))
			if event in values:
				cnt = int(tokens[0].split('.')[0])
				values[event] += value

			if (measure_ipc):
				if 'cycles' in tokens:
					c = value
				if 'instructions' in tokens:
					i = value
				if c > 1 and i > 1:
					ipc = i/c
					values['ipc_mean'] += ipc
					values['ipc_var'] += ipc ** 2
					c = 1
					i = 1
			line = fp.readline()

		if (measure_ipc):
			interval = config.getint(CFG_SECTION, "perf_interval")
			cnt /= interval / 1000
			values['ipc_mean'] /= cnt
			values['ipc_var'] = values['ipc_var']/cnt - values['ipc_mean'] ** 2

		os.remove("output.txt")
		fp.close()
		log.info("1. GOT THE FOLLOWING %(s)s", {'s': values})
		return values

	def run_and_perf_vm(self, vm):
		pid = self.get_vm_qemu_vcpu_pid(vm)
		if (pid == -1):
			log.error("Could not find the PID of VM: %(uuid)", {'uuid', vm.id})
			return
		events = config.get(CFG_SECTION, "perf_events")
		window = config.getint(CFG_SECTION, "perf_time_window")
		interval = config.getint(CFG_SECTION, "perf_interval")
		log.info("Running perf command with pid %(p)s...", {'p': pid})
		perf_cmd = "perf kvm --guest stat -e " + events + " -I " + str(interval) +\
		           " -o output.txt -p " + pid + " sleep " + str(window)
		os.system(perf_cmd)
		values = self.extract_measures(events)
		log.info("GOT THE FOLLOWING %(s)s", {'s': values})

	def isCharacterized(self, vm):
		return False

	def characterizeVM(self, vm):
		log.info("Characterizing VM: %(n)s %(u)s...", {'n': vm.name, 'u': vm.id})

		self.run_and_perf_vm(vm)

#		metadata = dict()
#		metadata['acticloudclass1'] = "quiet"
#		metadata['acticloudclass2'] = "insensitive"
#		self.nova.servers.set_meta(vm, metadata)
		log.info("Characterized VM: %(n)s %(u)s...", {'n': vm.name, 'u': vm.id})

	def get_vm_state(self, uuid):
		try:
			_vm = self.nova.servers.list(search_opts={'uuid': uuid})[0]
			return _vm.status
		except:
			return "FAILED"

	def wait_until_status(self, vm, status):
		log.info("Looping until status = %(stat)s", {'stat': status})
		while (self.get_vm_state(vm.id) != status):
			pass

	def execute(self):
		while (1):
			log.info("Executing characterization phase...")
			labVMs = self.getServerListByComputeNode(self.LAB_COMPUTE_NODE)
			for vm in labVMs:
				if (self.get_vm_state(vm.id) != "ACTIVE"):
					log.info("Ignoring VM %(n)s in state %(s)s", {'n': vm.name, 's': self.get_vm_state(vm.id)})
					continue

				if (not self.isCharacterized(vm)):
					self.characterizeVM(vm)
					vm.migrate()
					self.wait_until_status(vm, "VERIFY_RESIZE")
					vm.confirm_resize()
				else:
					log.info("VM %s is already characterized", vm.name)

			time.sleep(self.POLLING_PERIOD)

################################################################################
## The following are there for testing purposes
################################################################################
def configureLogging():
	logger = logging.getLogger()
	handler = logging.StreamHandler()
	formatter = logging.Formatter(
	                  '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	logger.setLevel(logging.INFO)
	return

def main(lab_compute_node):
	configureLogging()
	czagent = ActiCloudCharacterizationAgent(lab_compute_node)
	czagent.execute()

if __name__ == '__main__':
	hostname = socket.gethostname()
	if (len(sys.argv) == 2):
		hostname = sys.argv[1]
	main(hostname)
