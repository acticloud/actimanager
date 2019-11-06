import logging, time, operator, threading, pika, math, signal, sys

sys.path.append('../common/')
sys.path.append('../actidb/')
from config import *
from acticloudDB import ActiCloudDBClient
from openstack_client import OpenstackClient

overload_threshold1 = 0.26
overload_threshold2 = 0.51
os_limit = 4
pcpus = 20

class ACTiManagerExternal():
	def __init__(self, poll_period):
		self.logger = logging.getLogger(self.__class__.__name__) 

		## The queue where messages from internals are stored
		self.messages = []

		self.openstack_client = OpenstackClient()

		self.information_aggregator = InformationAggregator()
		self.poll_period = poll_period

	def start_rabbitmq_thread(self):
		self.logger.info("Starting rabbitmq consumer thread")
		self.rabbitmq_thread_done = 0
		self.rabbitmq_thread = threading.Thread(target = self.rabbitmq_consumer_thread)
		self.rabbitmq_thread.start()

	def stop_rabbitmq_thread(self):
		self.logger.info("Stopping rabbitmq consumer thread")
		self.rabbitmq_thread_done = 1
		self.rabbitmq_thread.join()

	def rabbitmq_consumer_thread(self):
		pika_creds = pika.credentials.PlainCredentials(RABBITMQ_USERNAME,
		                                               RABBITMQ_PASSWORD)
		pika_cp = pika.ConnectionParameters(RABBITMQ_IP, credentials=pika_creds)
		connection = pika.BlockingConnection(pika_cp)
		channel = connection.channel()
		channel.queue_declare(queue=RABBITMQ_ACTI_QUEUE_NAME)
		for message in channel.consume(RABBITMQ_ACTI_QUEUE_NAME, inactivity_timeout=5,
		                               auto_ack=True):
			if self.rabbitmq_thread_done:
				break
			if message == (None, None, None):
				continue
			method, properties, body = message
			self.logger.info("Received the following message: %s", body)
			self.messages.append(body)

	def check_internal_notification(self):
		if (len(self.messages) == 0):
			return None
		else:
			msg = self.messages[0]
			self.messages = self.messages[1:]
			return msg
	
	def doMigrate(self, vm_uuid, dst):
		self.openstack_client.live_migrate_vm(vm_uuid, dst)

	def find_server_overload_dst(self, vmid):
		'''
		Returns the most appropriate destination host for the given vm.
		By "most appropriate" we mean: 
		1. Not the current vm's host
		2. The least loaded (in vcpus) host
		3. On tie, the host with the least gold vcpus
		3. On second tie, we just return the first of the remaining hosts
		'''
		self.logger.info("Starting find_server_overload_dst(%s)", vmid)
		servers = self.information_aggregator.getComputeNodes()

		## Remove vm's current host
		current_host = self.information_aggregator.get_vm_current_host(vmid)
		if (current_host in servers):
			servers.remove(current_host)
		else:
			## Probably current host is None and the VM is deleted
			self.logger.info("Current host %s not in servers list %s",
			                  current_host, servers)
			return None

		## vcpus_per_server is a list of tuples with the following scheme:
		##  [ ("acticloud1", nr_total_vcpus, nr_gold_vcpus), (...), ... ]
		vcpus_per_server = []
		for server in servers:
			(gold_vcpus, silver_vcpus) = self.information_aggregator.getVcpusByComputeNode(server)
			vcpus_per_server.append((server, gold_vcpus+silver_vcpus, gold_vcpus))

		## Sort by nr_total_vcpus
		vcpus_per_server.sort(key=lambda x: x[1])

		## Keep only those with the min nr_total_vcpus
		vcpus_per_server = [ x for x in vcpus_per_server if x[1] == vcpus_per_server[0][1] ]
		self.logger.info("vcpus_per_server: %s", vcpus_per_server)

		## Now sort by nr_gold_vcpus
		vcpus_per_server.sort(key=lambda x: x[2])

		## We now have our destination
		dst = vcpus_per_server[0][0]
		dst_gold_vcpus = vcpus_per_server[0][2]
		dst_silver_vcpus = vcpus_per_server[0][1] - dst_gold_vcpus

		## Finally, check if the given VM can fit in the destination host
		vm_vcpus = self.information_aggregator.get_vm_nr_vcpus(vmid)
		if self.information_aggregator.is_gold_vm(vmid):
			if vm_vcpus <= (float(pcpus - dst_gold_vcpus) - float(dst_silver_vcpus) / os_limit):
				return dst
		else:
			if vm_vcpus <= ((pcpus - dst_gold_vcpus) * os_limit - dst_silver_vcpus):
				return dst

		## The VM does not fit in the destination host
		return None

	def handle_server_overload(self, events):
		servers = self.information_aggregator.getComputeNodes()
		ol_events = events['SERVER_OVERLOAD']
		messages = [0 for s in servers]
		for (host, vmid) in ol_events:
			## If the VM's current host is different than the one that sent the message,
			## the VM has probably already been migrated
			current_host = self.information_aggregator.get_vm_current_host(vmid)
			if (current_host != host):
				continue
			messages[servers.index(host)] += 1
		ol_servers = sum([int(bool(x)) for x in messages]) 
				
		overload_pct = float(ol_servers) / len(servers)
		handled = [False for s in servers]
		actions = 0
		if overload_pct < overload_threshold1:
			actions = ol_servers
		elif overload_pct < overload_threshold2:
			actions = ol_servers / 2
		else:
			# complain to remote cloud
			return

		for (host, vmid) in ol_events:
			if not actions:
				break
			if not handled[servers.index(host)]:
				actions -= 1
				dst = self.find_server_overload_dst(vmid)
				if dst == None:
					## FIXME nowhere to put the new VM, possibly pause it??
					continue
				self.doMigrate(vmid, dst)
				handled[servers.index(host)] = True

	def execute(self):
		while (1):
			events = dict()
			events["SERVER_OVERLOAD"] = []
			events["INTERFERENCE"] = []
			message = self.check_internal_notification()
			has_overload = False
			while message != None:
				self.logger.info("GOT MESSAGE: %s", message)
				message_type = message.split(' ')[0]
				if message_type == "SERVER_OVERLOAD":
					hostname = message.split(' ')[1]
					hint_vmid = message.split(' ')[2]
					events[message_type].append((hostname, hint_vmid))
					has_overload = True
				elif message_type == "INTERFERENCE":
					vmid = message.split()[1]
					dst = self.find_server_overload_dst(vmid)
					self.logger.info("Handling interference of VM %s by migrating to host %s", vmid, dst)
					if dst != None:
						self.doMigrate(vmid, dst)
					else:
						self.logger.info("Could not find a valid destination host for VM %s", vmid)
				else:
					pass
				message = self.check_internal_notification()

			if has_overload:
				self.handle_server_overload(events)

			self.logger.info("Sleeping for DP=%d seconds" % self.poll_period)
			time.sleep(self.poll_period)



class InformationAggregator():
	def __init__(self):
		self.logger = logging.getLogger(self.__class__.__name__)
		self.COMPUTE_NODES = ['acticloud1', 'acticloud2', 'acticloud3', 'acticloud4']
		self.acticlouddb_client = ActiCloudDBClient()
		self.openstack_client = OpenstackClient()

	def is_gold_vm(self, vmid):
		return self.acticlouddb_client.is_gold_vm(vmid, 1)

	def get_vm_nr_vcpus(self, vmid):
		return self.acticlouddb_client.get_nr_vcpus(vmid)

	def get_vm_current_host(self, vmid):
		return self.openstack_client.get_vm_current_host(vmid)

	def getServerListByComputeNode(self, computeNode):
		return self.openstack_client.get_vms_by_hostname(computeNode)

	def getGoldServerListByComputeNode(self, computeNode):
		all_servers = self.getServerListByComputeNode(computeNode)
		gold_servers = [x for x in all_servers if self.is_gold_vm(x)]
		return gold_servers

	def getSilverServerListByComputeNode(self, computeNode):
		all_servers = self.getServerListByComputeNode(computeNode)
		silver_servers = [x for x in all_servers if not self.is_gold_vm(x)]
		return silver_servers
	
	def getVcpusByComputeNode(self, computeNode):
		gold_vcpus = self.acticlouddb_client.get_nr_gold_vcpus_by_hostname(computeNode)
		silver_vcpus = self.acticlouddb_client.get_nr_silver_vcpus_by_hostname(computeNode)
		return (gold_vcpus, silver_vcpus)

	def getServerList(self):
		return self.openstack_client.get_vms()

	def getComputeNodes(self):
		return list(self.COMPUTE_NODES)

log = logging.getLogger("external")
external_instance = None

def signal_handler(signum, frame):
	log.info("-> Caught a signal, exiting...")
	external_instance.stop_rabbitmq_thread()
	sys.exit(1)

if __name__ == '__main__':
	## Setup the logging facility
	logging.basicConfig(stream=sys.stdout, level=logging.INFO,
	                    format='%(asctime)s - %(name)20s - %(message)s',
	                    datefmt='%Y-%m-%d.%H:%M:%S')
	logging.Formatter.converter = time.gmtime

	external_instance = ACTiManagerExternal(30)
	signal.signal(signal.SIGTERM, signal_handler)
	signal.signal(signal.SIGINT, signal_handler)
	external_instance.start_rabbitmq_thread()
	external_instance.execute()
