import logging, sys, numa
import pika, time, pytz
from datetime import datetime, timedelta
from enum import *
import threading

from System import *
from ActiManagerSystem import ActiManagerSystem
from GoldPerSocketSystem import GoldPerSocketSystem
from GoldNotOversubscribedSystem import GoldNotOversubscribedSystem 
from InterferenceDetector import InterferenceDetector

sys.path.append('../common/')
sys.path.append('../actidb/')
from config import *
from acticloudDB import ActiCloudDBClient
from openstack_client import OpenstackClient
import libvirt_client, event_logger, shell_command

# Variables FIXME get from config
INTERFERENCE_DETECTION_ENABLED = False
interference_cnt_lim = 5
decision_period = 30

UVISOR = False

class ACTiManagerInternal():
	def __init__(self, poll_period, compute_node_name, system_type):
		self.logger = logging.getLogger(self.__class__.__name__)

		if UVISOR:
			self.information_aggregator = uvisorInformationAggregator(compute_node_name, system_type)
			self.decision_maker = uvisorDecisionMaker(self.information_aggregator, compute_node_name)
		else:
			self.information_aggregator = InformationAggregator(compute_node_name, system_type)
			self.decision_maker = DecisionMaker(self.information_aggregator, compute_node_name)

		self.modeler = Modeler(compute_node_name, self.information_aggregator)
		self.poll_period = poll_period
		self.compute_node = compute_node_name

		ret_val = dict()
		model = self.modeler.newVmCheck(ret_val, None)
		if model:
			ret_val['new_vms'] = True
		self.decision_maker.decide_about_placement(ret_val)

		return

	def execute(self):
		## This is the main loop of ACTiManagerInternal
		while (1):
			self.logger.info("======================================================================>")
			self.logger.info("===> Execution Loop Starts")
			model = self.modeler.execute()
			self.modeler.report(model)
			self.decision_maker.decide(model)
			self.information_aggregator.report_events()

			self.logger.info("===> Execution Loop Ends")
			self.logger.info("===> Sleeping for %d seconds", self.poll_period)
			time.sleep(self.poll_period)

'''
This submodule is responsible for 'modeling' the cluster state.
This means that it just reports any problematic situation.
'''
class Modeler():
	def __init__(self, compute_node_name, information_aggregator):
		self.logger = logging.getLogger(self.__class__.__name__)
		self.information_aggregator = information_aggregator
		self.compute_node_name = compute_node_name

		## Initialize the interference detection module
		if (INTERFERENCE_DETECTION_ENABLED):
			self.interference_detector = InterferenceDetector(self.compute_node_name)

		return

	def newVmCheck(self, return_val, node_state):
		new_vms = []
		ret = False
		system = self.information_aggregator.get_system()
		vms = self.information_aggregator.getServerListByComputeNode(self.compute_node_name)
		for vm in vms:
			if vm.status != "ACTIVE":
				self.logger.info("VM is not ACTIVE (it is %s), moving on to the next", vm.status)
				continue
			nr_vcpus = self.information_aggregator.get_vm_nr_vcpus(vm)
			# FIXME: resize check only works for vcpu changes atm
			if vm.id not in system.vms or nr_vcpus != len(system.vms[vm.id].vcpus):
				try:
					system.deleteVM(vm.id)
				except:
					pass

				nr_vcpus = self.information_aggregator.get_vm_nr_vcpus(vm)
				cpu_util = self.information_aggregator.get_cpu_util(vm)
				is_gold = self.information_aggregator.is_gold_vm(vm)
				is_noisy = self.information_aggregator.is_noisy_vm(vm)
				is_sensitive = self.information_aggregator.is_sensitive_vm(vm)
				cost_fun = self.information_aggregator.get_cost_function(vm) if not is_gold else 1

				## GOLD VMs are monitored for interference
				if (INTERFERENCE_DETECTION_ENABLED and is_gold):
					self.interference_detector.add_vm(vm)

				# Create a Vm Node object without placing it in the tree
				vmnode = Vm(vm.id, nr_vcpus, cpu_util, is_gold, is_noisy, is_sensitive,
				            cost_fun, vm)
				new_vms.append(vmnode)
				ret = True
		if (len(new_vms) > 0):
			return_val['new_vm_list'] = list(new_vms)

			# FIXME: workaround the network limitations of current kMAX setup, by hotplugging a SLIRP interface post-boot
			def attach_helper():
				# FIXME: ugly workaround for the fact that early boot pci hotplug doesn't work reliably
				time.sleep(30)
				for vm in new_vms:
				try:
					libvirt_instance_name = getattr(vm.openstack, 'OS-EXT-SRV-ATTR:instance_name')
					with libvirt_client.LibVirtConnection(self.information_aggregator.hostname, "qemu+ssh") as libvconn:
						libvinstance = libvirt_client.LibVirtInstance(libvconn, str(libvirt_instance_name))
						libvinstance.attach_device("")
				except Exception as e:
					self.logger.info("=================> Could not attach slirp nic for vm %s (%s)", vm.id, e)

			t = threading.Thread(target=attach_helper)
			t.start()

		return ret

	def removedVmCheck(self, return_val, node_state):
		removed_vms = []
		ret = False
		vms = self.information_aggregator.getServerListByComputeNode(self.compute_node_name)
		running_ids = [vm.id for vm in vms]
		system = self.information_aggregator.get_system()
		for key in system.vms:
			if key not in running_ids:
				removed_vms.append(key)
				ret = True

				## Remove VM from interference detector
				if (INTERFERENCE_DETECTION_ENABLED):
					self.interference_detector.remove_vm_by_uuid(key)
		if len(removed_vms) > 0:
			return_val['removed_vm_list'] = list(removed_vms)
		return ret

	def interferenceCheck(self, return_val, node_state, has_new_vms):
		ret = False
		affected_vms = []
		system = self.information_aggregator.get_system()
		for vmid in system.vms:
			vm = system.vms[vmid]
			if (vm.is_gold):
				self.logger.info("Checking VM %s for INTERFERENCE", vmid)
				suffers = self.interference_detector.check_interference(vm.openstack)
				self.logger.info("VM %s INTERFERENCE: %s", vmid, suffers)
				if (suffers):
					if not has_new_vms or vm.interference_cnt > 0:
						vm.interference_cnt += 1
						self.logger.info("Interference Detected at: %s, DP %d of %d" % \
										(vm, vm.interference_cnt, interference_cnt_lim))
					if vm.interference_cnt == interference_cnt_lim:
						vm.interference_cnt = 0
						affected_vms.append(vm)
						ret = True
				else:
					vm.interference_cnt = 0
		return_val['interference_vm_list'] = list(affected_vms)
		return ret

	def execute(self):
		## Stop interference detector
		if (INTERFERENCE_DETECTION_ENABLED):
			self.interference_detector.stop_perf_threads()

		return_val = dict()
		node_state = None
		has_new_vms = False
		if self.removedVmCheck(return_val, node_state):
			return_val['removed_vms'] = True
		if self.newVmCheck(return_val, node_state):
			return_val['new_vms'] = True
			has_new_vms = True
		if (INTERFERENCE_DETECTION_ENABLED and self.interferenceCheck(return_val, node_state, has_new_vms)):
			return_val['interference'] = True

		## Start interference detector
		if (INTERFERENCE_DETECTION_ENABLED):
			self.interference_detector.start_perf_threads()

		return return_val

	def report(self, model):
		self.logger.info("======> Starting report of Modeler's output:")
		model_empty = 1
		if 'new_vms' in model:
			self.logger.info("======> New VMs detected")
			self.logger.info("======> New VMs: %s" % model['new_vm_list'])
			model_empty = 0
		if 'interference' in model:
			vms = model['interference_vm_list']
			self.logger.info("======> Interference Detected. Affected VMs: %s" % vms)
			model_empty = 0
		if 'removed_vms' in model:
			vms = model['removed_vm_list']
			self.logger.info("======> Deleted VMs: %s" % vms)
			model_empty = 0
		if model_empty:
			self.logger.info("======> Nothing new ...")
		self.logger.info("======> End of Modeler's output")

class DecisionMaker():
	'''
	DecisionMaker is responsible for translating the Modeler's output to actions.
	'''
	def __init__(self, information_aggregator, hostname):
		self.logger = logging.getLogger(self.__class__.__name__)
		self.information_aggregator = information_aggregator
		self.hostname = hostname

		self.logger.info("Decision Maker initialized successfully")

	def pin_vcpu(self, vm, vcpu, pcpus):
		self.logger.debug("======> Pinning vcpu %d in pcpus %s", vcpu, pcpus)
		try:
			libvirt_instance_name = getattr(vm, 'OS-EXT-SRV-ATTR:instance_name')
			with libvirt_client.LibVirtConnection(self.hostname, "qemu+ssh") as libvconn:
				libvinstance = libvirt_client.LibVirtInstance(libvconn, str(libvirt_instance_name))
				libvinstance.map_instance_vcpu(vcpu, pcpus)
			return True
		except:
			self.logger.info("=================> Could not pin vcpu %d in pcpus %s", vcpu, pcpus)
			return False

	def migrate_vm_pages(self, vm, dst_node, src_node = "all"):
		command = "ssh %s /usr/bin/migratepages %s %s %s" % (self.hostname, str(vm), 
		                                                     str(src_node), str(dst_node))
		ret = shell_command.run_shell_command(command)

	def numa_dst_decide(self, prev_cores, new_cores):
		prev_numa = list()
		new_numa = list()
		for i in range(len(prev_cores)):
			if prev_cores[i]: # because prev_cores is a mask: [0,0,1,1,...] -> runs on core 2,3...
				prev_numa.append(self.information_aggregator.get_dst_numa_node_from_pcpu(i))
		for dst in new_cores:
			new_numa.append(self.information_aggregator.get_dst_numa_node_from_pcpu(dst))
		if len(prev_numa) > len(new_numa): #FIXME ypap 
			return ('all', str(max(set(new_numa), key = new_numa.count)))
		moves = dict()
		for i in range(len(prev_numa)):
			moves[i] = (prev_numa[i], new_numa[i])
		numa_dst = dict()
		for node in set(prev_numa):
			targets = []
			for i in moves:
				if moves[i][0] == node:
					targets.append(moves[i][1])
			if set(targets) != set([node]):
				dst = max(set(targets), key = targets.count)
				if dst != node:
					numa_dst[node] = dst
		if len(set(numa_dst.values())) == 1:
			return ("all", numa_dst.values()[0])
		return (str(numa_dst.keys()).replace('[','').replace(']','').replace(' ',''),
				str(numa_dst.values()).replace('[','').replace(']','').replace(' ', ''))

	def move_vm(self, moves):
		self.logger.info("======> Moves START: %s", moves)
		ret = False
		system = self.information_aggregator.get_system()
		for move in moves:
			vmnode = move[0]
			self.logger.debug("======> Moving VM %s", vmnode.id)
			vm_to_move = vmnode.openstack
			prev_map = self.information_aggregator.getVMVcpuMapping(vm_to_move)
			## The VM may have been deleted in the meanwhile
			if prev_map == None:
				if vmnode.id in system.vms:
					system.deleteVM(vmnode.id)
					continue

			if (isinstance(system, GoldNotOversubscribedSystem) or \
			    isinstance(system, GoldPerSocketSystem)) and not vmnode.is_gold:
				for vcpu_id in range(len(vmnode.vcpus)):
					ret = self.pin_vcpu(vm_to_move, vcpu_id, move[1])
					if ret == False:
						break
			else:
				for vcpu, dst in enumerate(move[1]):
					if UVISOR:
						ret = self.pin_vcpu(vm_to_move, vcpu, dst)
					else:
						ret = self.pin_vcpu(vm_to_move, vcpu, [dst])
					if ret == False:
						break

			self.logger.debug("======> Moving VM %s returned %d", vmnode.id, ret)
			if ret == False:
				if vmnode.id in system.vms:
					system.deleteVM(vmnode.id)
				break

			(src_node, dst_node) = self.numa_dst_decide(prev_map, move[1])
			vm_pid = self.information_aggregator.get_pid_from_vm_id(vm_to_move)
			if src_node != "":
				self.migrate_vm_pages(vm_pid, dst_node, src_node)
			vmnode.last_move = datetime.now()
		self.logger.info("======> Moves END: %s", moves)

	def _send_message_to_external(self, msg):
		self.logger.info("======> Sending message to external: %s", msg)
		pika_creds = pika.credentials.PlainCredentials(RABBITMQ_USERNAME,
		                                               RABBITMQ_PASSWORD)
		pika_cp = pika.ConnectionParameters(RABBITMQ_IP, credentials=pika_creds)
		connection = pika.BlockingConnection(pika_cp)
		rabbitmq_channel = connection.channel()
		rabbitmq_channel.queue_declare(queue=RABBITMQ_ACTI_QUEUE_NAME)
		rabbitmq_channel.basic_publish(exchange='',
		                               routing_key=RABBITMQ_ACTI_QUEUE_NAME,
		                               body=msg)
		return

	def vm_placement(self, vms):
		system = self.information_aggregator.get_system()
		overload_detected = False
		for vm in vms:
			moves = system.placeVM(vm)
			overload_detected = overload_detected or system.server_overload
			# dst is an empty list if no suitable destinations were found
			if moves == []:
				self.logger.info("======> Empty moves for PLACEMENT of VM %s. Notifying External...", vm.id)
				self._send_message_to_external("PLACEMENT %s" % vm.id)
			else:
				# moves: List[(Vm, core_ids: List[int])]
				self.move_vm(moves)
		return overload_detected

	def check_for_server_overload(self):
		system = self.information_aggregator.get_system()
		vms = system.vms.values()

		## Sort the list of VMs by a) silver/gold, b) quiet/noisy, c) nr_vcpus (descending)
		if 0 in [v.is_gold for v in vms]:
			vms = sorted(vms, key=lambda x: (x.is_gold == 0, x.is_noisy == 0, x.vcpus), reverse=True)
		## if there are only gold VMs, sort by a) quiet/noisy c) nr_vcpus (ascending)
		else:
			vms = sorted(vms, key=lambda x: (x.is_noisy == 1, x.vcpus))
		vm = vms[0]

		if vm.is_gold and len(vm.vcpus) > 4:
			self.logger.info("======> Did not send SERVER OVERLOAD. VM %s will not be migrated" %vm.id)
		else:
			self.logger.info("======> Sending SERVER OVERLOAD message. VM to migrate: '%s'" % vm.id)
			self._send_message_to_external("SERVER_OVERLOAD %s %s" %(self.information_aggregator.hostname, vm.id))
			system.server_overload = False

	def decide_about_interference(self, model):
		if (not 'interference' in model):
			return
		system = self.information_aggregator.get_system()
		vms = model['interference_vm_list']
		handle_vms = list()
		for vm in vms:
#			if datetime.now() - vm.last_move < timedelta(seconds=decision_period *
#			                                                     interference_cnt_lim * 2):
#				self.logger.info("======> VM wants to move within time limit." + \
#								 " Notifying external '%s'", "INTERFERENCE %s" % vm.id)
#				self._send_message_to_external("INTERFERENCE %s" % vm.id)
#				self.information_aggregator.update_moves(vm)
#			else:

			if len(vm.vcpus) < 4 and not vm.bubble:
				self.logger.info("===> Interference at: %s, injecting %s bubble vCPUS", str(vm), str(4 - len(vm.vcpus)))
				system.bubble_boost(vm)
				handle_vms.append(vm)
			elif len(vm.vcpus) > 3:
				self.logger.info("===> Interference at: %s, too large, NO ACTION", str(vm))
			elif vm.bubble:
				self.logger.info("===> Interference at: %s, already assigned a bubble", str(vm))
		overload_detected = self.vm_placement(handle_vms)
		if overload_detected:
			self.check_for_server_overload()

	def decide_about_placement(self, model):
		if (not 'new_vms' in model):
			return
		vms = model['new_vm_list']
		overload_detected = self.vm_placement(vms)
		if overload_detected:
			self.check_for_server_overload()

	def decide_about_removal(self, model):
		if (not 'removed_vms' in model):
			return
		vms = model['removed_vm_list']

		system = self.information_aggregator.get_system()
		for key in vms:
			system.deleteVM(key)

		moves = []
		if isinstance(system, ActiManagerSystem):
			moves = system.rebalance()
		else:
			moves = system.repin_silvers() 

		if moves:
			self.move_vm(moves)

	def decide(self, model):
		## Decide about the actions to be performed here.
		self.decide_about_removal(model)
		if (INTERFERENCE_DETECTION_ENABLED):
			self.decide_about_interference(model)
		self.decide_about_placement(model)

#		system = self.information_aggregator.get_system()
#		if isinstance(system, ActiManagerSystem):
#			moves = system.rebalance_global()
#			if moves:
#				self.move_vm(moves)

class InformationAggregator():
	def __init__(self, compute_node_name, system_type):
		global INTERFERENCE_DETECTION_ENABLED
		self.logger = logging.getLogger(self.__class__.__name__)
		self.hostname = compute_node_name

		self.compute_node_name = compute_node_name

		self.system_type = system_type
		# FIXME: make hardware topology tunable
		if system_type == "actistatic" or system_type == "actifull":
			if system_type == "actifull":
				INTERFERENCE_DETECTION_ENABLED = True
			self.system = ActiManagerSystem([2, 1, 4], compute_node_name)
		elif system_type == "gps":
			self.system = GoldPerSocketSystem([2, 1, 4], compute_node_name)
		elif system_type == "gno":
			self.system = GoldNotOversubscribedSystem([2, 1, 4], compute_node_name)
		else:
			self.logger.error("Wrong system_type given: %s", system_type)
			sys.exit(1)

		self.acticlouddb_client = ActiCloudDBClient()
		self.openstack_client = OpenstackClient()
		return

	def get_system(self):
		return self.system

	def report_events(self):
		if ("acti" in self.system_type):
			event_logger.log_event({'event': 'internal-profit-report',
									'profit-value': self.system.cur_profit, 'hostname': self.hostname})
			esd_dict = dict()
			for vm in self.system.vms:
				esd_dict[vm] = [v.esd for v in self.system.vms[vm].vcpus]
			event_logger.log_event({'event': 'internal-esd-report',
									'values': esd_dict, 'hostname': self.hostname})

	def get_pid_from_vm_id(self, vm):
		command = "nova show %s | grep -i 'OS-EXT-SRV-ATTR:instance_name' | awk -F'|' '{print $3}'" % str(vm.id)
		libvirt_instance_name = shell_command.run_shell_command(command).strip()
		command = "ssh %s ps -ef | grep %s | grep \"qemu-system\" | grep -v grep | awk '{print $2}'" % (self.hostname, libvirt_instance_name)
		pid = shell_command.run_shell_command(command).strip()
		return pid

	def get_dst_numa_node_from_pcpu(self, pcpu_id):
		# FIXME: numa module doesn't work on KMAX big.LITTLE platform
		return 0 if pcpu_id < 4 else 1

		#module numa has not implemented numa_node_of_cpu() call of numa(3) library
		for i in range(0, numa.get_max_node() + 1):
			if pcpu_id in numa.node_to_cpus(i):
				return i

	def print_vcpu_to_pcpu_mapping(self):
		p_mapping = []
		for vm in self.getServerListByComputeNode(self.compute_node_name):
			vm_mapping = self.getVMVcpuMapping(vm)
			for i in range(len(vm_mapping)):
				p_mapping.append(0)
			break
		for vm in self.getServerListByComputeNode(self.compute_node_name):
			vm_mapping = self.getVMVcpuMapping(vm)
			for i in range(len(vm_mapping)):
				if vm_mapping[i]:
					if self.is_gold_vm(vm):
						p_mapping[i] += 10
					else:
						p_mapping[i] += 1
		self.logger.info("Physical CPU mapping: %s" % p_mapping)
		return

	def is_noisy_vm(self, vm):
		is_noisy = self.acticlouddb_client.is_noisy_vm(vm.id)
		return is_noisy
	def is_sensitive_vm(self, vm):
		is_sensitive = self.acticlouddb_client.is_sensitive_vm(vm.id)
		return is_sensitive
	def is_gold_vm(self, vm):
		is_gold = self.acticlouddb_client.is_gold_vm(vm.id, 1)
		return is_gold
	def get_vm_nr_vcpus(self, vm):
		return self.acticlouddb_client.get_nr_vcpus(vm.id)
	def get_cost_function(self, vm):
		cost_function = self.acticlouddb_client.cost_function(vm.id)
		return cost_function

	def get_cpu_util(self, vm):
		return 1.0 # FIXME
		cpu_util = self.acticlouddb_client.cpu_util(vm.id)
		return cpu_util

	def update_moves(self, vm): # vm: Vm class instance
		prev_moves = self.acticlouddb_client.get_moves(vm.id)
		self.acticlouddb_client.set_moves(vm.id, prev_moves + vm.moves)

	def getServerListByComputeNode(self, computeNode):
		return self.openstack_client.get_vms_by_hostname(computeNode)

	def getServerList(self):
		return self.openstack_client.get_vms()

	def getVMVcpuMapping(self, vm):
		try:
			libvirt_instance_name = getattr(vm, 'OS-EXT-SRV-ATTR:instance_name')
			with libvirt_client.LibVirtConnection(self.hostname, "qemu+ssh") as libvconn:
				libvinstance = libvirt_client.LibVirtInstance(libvconn, str(libvirt_instance_name))
				return list(libvinstance.get_instance_mapping()[0])
		except:
			self.logger.info("=================> Could not get vcpu mapping of VM %s", vm.id)
			return None

if __name__ == '__main__':
	system_types = ["actistatic", "actifull", "gps", "gno"]
	global logger

	if len(sys.argv) != 3:
		print "usage: %s <compute_node_hostname> <system_type>" % sys.argv[0]
		print "       system_type can be one of: %s", system_types
		sys.exit(1)

	hostname = sys.argv[1]
	system_type = sys.argv[2]

	if system_type not in system_types:
		print "Wrong system_type given: %s (available are: %s)" % (system_type, system_types)
		sys.exit(1)

	## Setup the logging facility
	logging.basicConfig(stream=sys.stdout, level=logging.INFO,
	                    format='%(asctime)s - ' + system_type + ' - %(name)20s - %(message)s',
	                    datefmt='%Y-%m-%d.%H:%M:%S')
	logging.Formatter.converter = time.gmtime
	logger = logging.getLogger("actimanager-internal-%s" % hostname)

	internal = ACTiManagerInternal(decision_period, hostname, system_type)
	internal.execute()
