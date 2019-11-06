# Copyright (c) 2011-2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as logging
from nova.scheduler import filters
from novaclient import client as novaclient
import sys, math, os, datetime

from acticloud_calculate_profit import *
sys.path.append('/home/jim/jimsiak/common/') ## FIXME this should be removed
sys.path.append('/home/jim/jimsiak/actidb/')
from config import *
from acticloudDB import ActiCloudDBClient
import event_logger as acticloud_event_logger

LOG = logging.getLogger(__name__)

ACTICLOUD_OVERSUBSCRIPTION = SILVER_OVERSUBSCRIPTION_RATIO

class ActicloudNumGoldSilverFilter(filters.BaseHostFilter):
	"""
	ACTiCLOUD filter.
	Part of ACTiManager external.
	"""

	# list of hosts doesn't change within a request
	run_filter_once_per_request = True

	def __init__(self):
		LOG.info("Hello from ACTICLOUD Filter __init__")
		self.acticlouddb_client = ActiCloudDBClient()
		self.nova = novaclient.Client("2", **get_nova_creds())

	def host_passes(self, host_state, spec_obj):
		hostname = host_state.host
		vm_uuid = spec_obj.instance_uuid
		flavor_id = spec_obj.flavor.flavorid
		nr_gold_vms = self.acticlouddb_client.get_nr_gold_vms_by_hostname(hostname)
		nr_gold_vcpus = self.acticlouddb_client.get_nr_gold_vcpus_by_hostname(hostname)
		nr_silver_vcpus= self.acticlouddb_client.get_nr_silver_vcpus_by_hostname(hostname)
		is_gold_vm = flavor_id in ["1001", "1002", "1004", "1008"]

		nr_vcpus_host = host_state.vcpus_total
		nr_vcpus_instance = spec_obj.vcpus

#		## FIXME remove me
#		if (hostname != "acticloud1"):
#			return False

		## How many vcpus do silver VMs occupy when oversubscribed?
		nr_silver_vcpus_ovs = int(math.ceil(float(nr_silver_vcpus) / ACTICLOUD_OVERSUBSCRIPTION))
		free_vcpus = nr_vcpus_host - (nr_gold_vcpus + nr_silver_vcpus_ovs)
		ret = False
		if is_gold_vm:
			if free_vcpus >= nr_vcpus_instance:
				ret = True 
		else: # is silver vm
			if free_vcpus >= math.ceil(nr_vcpus_instance / ACTICLOUD_OVERSUBSCRIPTION):
				ret = True
			else:
				free_oversubscribed_vcpus = int(nr_silver_vcpus_ovs * ACTICLOUD_OVERSUBSCRIPTION) - nr_silver_vcpus
				if free_oversubscribed_vcpus >= nr_vcpus_instance:
					ret = True

		if ret:
			LOG.info("DOES FIT IN HOST %s", hostname)
		else:
			LOG.info("DOES NOT FIT IN HOST %s", hostname)
		return ret

class ActicloudProfitFilter(ActicloudNumGoldSilverFilter):
	"""
	ACTiCLOUD filter.
	Part of ACTiManager external.
	"""

	def host_passes(self, host_state, spec_obj):
		hostname = host_state.host
		vm_uuid = spec_obj.instance_uuid
		flavor_id = spec_obj.flavor.flavorid
		nr_gold_vms = self.acticlouddb_client.get_nr_gold_vms_by_hostname(hostname)
		nr_gold_vcpus = self.acticlouddb_client.get_nr_gold_vcpus_by_hostname(hostname)
		nr_silver_vcpus= self.acticlouddb_client.get_nr_silver_vcpus_by_hostname(hostname)
		is_gold_vm = flavor_id in ["1001", "1002", "1004", "1008"]

		nr_vcpus_host = host_state.vcpus_total
		nr_vcpus_instance = spec_obj.vcpus

		LOG.info("============= ActicloudProfitFilter %s ==========================>", hostname)

		## If the new VM does not fit return False
		if not super(ActicloudProfitFilter, self).host_passes(host_state, spec_obj):
			LOG.info("=======================================================>")
			return False

		## If host was empty we don't need to check its profit
		nr_silver_vcpus_ovs = int(math.ceil(float(nr_silver_vcpus) / ACTICLOUD_OVERSUBSCRIPTION))
		free_vcpus = nr_vcpus_host - (nr_gold_vcpus + nr_silver_vcpus_ovs)
		if free_vcpus == nr_vcpus_host:
			LOG.info("Host %s is empty, so it passes the filter", hostname)
			LOG.info("=======================================================>")
			return True

		''' VM fits in the node, now let's check if it will give profit '''
		vms = list(self.acticlouddb_client.get_vms_by_hostname(hostname))

		## Calculate current host_profit
		host_profit_before = calculate_host_profit(vms, nr_vcpus_host)

		new_vm_uuid = vm_uuid
		new_vm = self.nova.servers.get(new_vm_uuid)
		new_vm_vcpus = int(self.nova.flavors.get(new_vm.flavor['id']).vcpus)
		new_vm_is_gold = int(new_vm.metadata.get('is_gold')) or 0
		new_vm_is_noisy = int(new_vm.metadata.get('is_noisy')) or 0
		new_vm_is_sensitive = int(new_vm.metadata.get('is_sensitive')) or 0
		vms.append({'id': new_vm_uuid, 'hostname': hostname, 'nr_vcpus': new_vm_vcpus,
		            'is_gold': new_vm_is_gold, 'is_noisy': new_vm_is_noisy,
		            'is_sensitive': new_vm_is_sensitive})

		## Calculate host_profit with new VM
		host_profit_after = calculate_host_profit(vms, nr_vcpus_host)
		host_profit_diff = host_profit_after - host_profit_before
		LOG.info("New profit: %.2f Previous profit: %.2f Difference: %.2f",
		         host_profit_after, host_profit_before, host_profit_diff)
		LOG.info("=======================================================>")

		time_now = datetime.datetime.utcnow().strftime("%Y-%m-%d.%X")
		acticloud_event_logger.log_event({'event': 'acticloud-external-openstack-filter-profit-report',
		                                  'profit-before': host_profit_before,
		                                  'profit-after': host_profit_after,
		                                  'profit-diff': host_profit_diff, 'hostname': hostname,
		                                  'time': time_now, 'new-vm-uuid': new_vm_uuid})

		if host_profit_diff <= 0:
			return False
		else:
			return True


class ActicloudGoldServerIsolationFilter(filters.BaseHostFilter):
	"""
	ACTiCLOUD filter.
	Part of ACTiManager external.
	Each gold VM occupies one compute node. Silver ones can be put altogether.
	"""

	# list of hosts doesn't change within a request
	run_filter_once_per_request = True

	def __init__(self):
		LOG.info("Hello from ACTICLOUD GoldServerIsolationFilter __init__")
		self.nova = novaclient.Client("2", **get_nova_creds())

	def host_passes(self, host_state, spec_obj):
		hostname = host_state.host
		vm_uuid = spec_obj.instance_uuid
		flavor_id = spec_obj.flavor.flavorid
		is_gold_vm = flavor_id in ["1001", "1002", "1004", "1008"]

		host_vms = self.nova.servers.list(search_opts={'host': hostname})
		nr_host_vms = len(host_vms)

		ret = 1
		if is_gold_vm and nr_host_vms > 0:
			ret = 0
		else:
			nr_gold_vms = 0
			for vm in host_vms:
				if "gold" in vm.name:
					nr_gold_vms += 1
			if nr_gold_vms > 0:
				ret = 0

		if ret:
			log_str = "VM %(uuid)s (%(is_gold)s) fits in host %(host)s"
		else:
			log_str = "VM %(uuid)s (%(is_gold)s) DOES NOT fit in host %(host)s"
		LOG.info(log_str, {"uuid": vm_uuid,
		         "is_gold": "GOLD" if is_gold_vm else "SILVER",
		         "host": hostname})

		return ret

class ActicloudGoldSocketIsolationFilter(filters.BaseHostFilter):
	"""
	ACTiCLOUD filter.
	Part of ACTiManager external.
	Each gold VM occupies one socket (so 2 gold per server). Silver ones can be put altogether.
	"""

	# list of hosts doesn't change within a request
	run_filter_once_per_request = True

	def __init__(self):
		LOG.info("Hello from ACTICLOUD GoldSocketIsolationFilter __init__")
		self.nova = novaclient.Client("2", **get_nova_creds())

	def host_passes(self, host_state, spec_obj):
		hostname = host_state.host
		vm_uuid = spec_obj.instance_uuid
		flavor_id = spec_obj.flavor.flavorid
		is_gold_vm = flavor_id in ["1001", "1002", "1004", "1008"]

		host_vms = self.nova.servers.list(search_opts={'host': hostname})
		nr_host_vms = len(host_vms)
		nr_gold_vms = 0
		for vm in host_vms:
			if vm.flavor['id'] in ["1001", "1002", "1004", "1008"]:
				nr_gold_vms += 1
				LOG.info("VM: %(vm)s", {"vm": vm.flavor['id']})
		nr_silver_vms = nr_host_vms - nr_gold_vms

		ret = 1
		if nr_gold_vms >= 2:
			ret = 0
		elif is_gold_vm and nr_gold_vms == 1 and nr_host_vms > 1:
			ret = 0

		if ret:
			log_str = "VM %(uuid)s (%(is_gold)s) fits in host %(host)s"
		else:
			log_str = "VM %(uuid)s (%(is_gold)s) DOES NOT fit in host %(host)s"
		LOG.info(log_str, {"uuid": vm_uuid,
		         "is_gold": "GOLD" if is_gold_vm else "SILVER",
		         "host": hostname})

		return ret
