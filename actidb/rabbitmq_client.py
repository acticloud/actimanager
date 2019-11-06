#!/usr/bin/env python
import sys, argparse, time, logging, hashlib, json, random
from kombu import BrokerConnection, Exchange, Queue
from kombu.mixins import ConsumerMixin

from acticloudDB import ActiCloudDBClient
sys.path.append('../common/')
from config import *

## Setup the logging facility
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                format='%(asctime)s - %(name)20s - %(message)s',
                datefmt='%Y-%m-%d.%H:%M:%S')
logging.Formatter.converter = time.gmtime
logger = logging.getLogger("rabbitmq_client")

class NotificationsDump(ConsumerMixin):

	def __init__(self, connection):
		self.acticloudDBClient = ActiCloudDBClient()
		self.connection = connection
		return

	def db_insert_vm(self, vm_uuid, vm_name, flavor_id, hostname, nr_vcpus, metadata):
		is_gold = int(metadata['is_gold']) if 'is_gold' in metadata else 0
		is_noisy = int(metadata['is_noisy']) if 'is_noisy' in metadata else 0
		is_sensitive = (metadata['is_sensitive']) if 'is_sensitive' in metadata else 0
		cost_function = 0
		if is_gold or "fixed_time" in vm_name:
			cost_function = 1
		self.acticloudDBClient.insert_vm(vm_uuid, hostname, nr_vcpus, is_gold, is_noisy, is_sensitive, cost_function)

	def db_remove_vm(self, vm_uuid):
		self.acticloudDBClient.remove_vm(vm_uuid)

	def db_update_vm_migration(self, vm_uuid, new_host):
		self.acticloudDBClient.set_vm_attribute(vm_uuid, "hostname", new_host)
		self.acticloudDBClient.inc_vm_attribute(vm_uuid, "no_migrations")

	def get_consumers(self, consumer, channel):
		exchange = Exchange(EXCHANGE_NAME, type="topic", durable=False)
		queue = Queue(QUEUE_NAME, exchange, routing_key = ROUTING_KEY,\
		              durable=False, auto_delete=False, no_ack=True)
		return [ consumer(queue, callbacks = [ self.on_message ]) ]

	def on_message(self, body, message):
		json_body = json.loads(body["oslo.message"])
		event_type = json_body["event_type"]
		logger.info('Event_type: %s' % event_type)
		if (event_type == "compute.instance.create.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			vm_name = json_body["payload"]["display_name"]
			flavor_id = json_body["payload"]["instance_flavor_id"]
			hostname = json_body["payload"]["host"]
			nr_vcpus = json_body["payload"]["vcpus"]
			vm_metadata = json_body["payload"]["metadata"]
			self.db_insert_vm(vm_uuid, vm_name, flavor_id, hostname, nr_vcpus, vm_metadata)
			logger.info("VM " + vm_uuid + " just created")
		elif (event_type == "compute.instance.delete.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			self.db_remove_vm(vm_uuid)
			logger.info("VM " + vm_uuid + " just got deleted")
		elif (event_type == "compute.instance.pause.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			logger.info("VM " + vm_uuid + " just got paused")
		elif (event_type == "compute.instance.unpause.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			logger.info("VM " + vm_uuid + " just got unpaused")
		elif (event_type == "compute.instance.power_off.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			logger.info("VM " + vm_uuid + " just got powered off")
		elif (event_type == "compute.instance.power_on.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			logger.info("VM " + vm_uuid + " just got powered on")
		elif (event_type == "compute.instance.live_migration.post.dest.end"):
			vm_uuid = json_body["payload"]["instance_id"]
			hostname = json_body["payload"]["host"]
			logger.info("VM %s MIGRATED TO %s" % (vm_uuid, hostname))
			self.db_update_vm_migration(vm_uuid, hostname)
		elif (event_type == "compute.instance.update"):
			host_id = ""
		else:
			logger.info('Unknown message')

if __name__ == "__main__":
	logger.info("Connecting to broker {}".format(RABBITMQ_BROKER_URI))
	with BrokerConnection(RABBITMQ_BROKER_URI) as connection:
		NotificationsDump(connection).run()
