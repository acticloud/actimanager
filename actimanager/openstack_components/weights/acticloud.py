# Copyright (c) 2011 OpenStack Foundation
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
"""
ACTiCLOUD Weigher.
"""
from oslo_log import log as logging
from nova.scheduler import weights
from novaclient import client as novaclient
from acticloud_calculate_profit import *
import sys, time, math

sys.path.append('/home/jim/jimsiak/common/') ## FIXME this should be removed
sys.path.append('/home/jim/jimsiak/actidb/')
from config import *
from acticloudDB import ActiCloudDBClient

LOG = logging.getLogger(__name__)

ACTICLOUD_OVERSUBSCRIPTION = 4.0

class ActicloudWeigher(weights.BaseHostWeigher):
	def __init__(self):
		LOG.info("Hello from ActicloudWeigher __init__")
		self.acticlouddb_client = ActiCloudDBClient()
		self.nova = novaclient.Client("2", **get_nova_creds())

	def _weigh_object(self, host_state, weight_properties):
		"""Higher weights win."""
		## Get everything needed from the acticloudDB
		hostname = host_state.host
		nr_vcpus_host = host_state.vcpus_total
		vms = list(self.acticlouddb_client.get_vms_by_hostname(hostname))

		LOG.info("============ ActicloudWeigher %s ===================>", hostname)

		## Calculate current host_profit
		host_profit_before = calculate_host_profit(vms, nr_vcpus_host)

		## Get everything needed from openstack
		new_vm_uuid = weight_properties.instance_uuid
		new_vm = self.nova.servers.get(new_vm_uuid)
		new_vm_vcpus = self.nova.flavors.get(new_vm.flavor['id']).vcpus
		new_vm_is_gold = new_vm.metadata.get('is_gold') or 0
		new_vm_is_noisy = new_vm.metadata.get('is_noisy') or 0
		new_vm_is_sensitive = new_vm.metadata.get('is_sensitive') or 0
		vms.append({'id': new_vm_uuid, 'hostname': hostname, 'nr_vcpus': new_vm_vcpus,
		            'is_gold': new_vm_is_gold, 'is_noisy': new_vm_is_noisy,
		            'is_sensitive': new_vm_is_sensitive})

		## Calculate host_profit with new VM
		host_profit_after = calculate_host_profit(vms, nr_vcpus_host)

		## If the new VM is the only one in the server, we need to include the
		## cost of opening a server
		if len(vms) == 1:
			host_profit_after -= SERVER_COST

		host_profit_diff = host_profit_after - host_profit_before
		LOG.info("New profit: %.2f Previous profit: %.2f Difference: %.2f",
		         host_profit_after, host_profit_before, host_profit_diff)
		LOG.info("=======================================================>")
		return host_profit_diff

class ActicloudGoldWeigher(weights.BaseHostWeigher):
	def __init__(self):
		LOG.info("Hello from Gold __init__")
		self.acticlouddb_client = ActiCloudDBClient()

	def _weigh_object(self, host_state, weight_properties):
		hostname = host_state.nodename
		nr_gold_vcpus = self.acticlouddb_client.get_nr_gold_vcpus_by_hostname(hostname)
		nr_silver_vcpus = self.acticlouddb_client.get_nr_silver_vcpus_by_hostname(hostname)
		nr_silver_vcpus_ovs = int(math.ceil(float(nr_silver_vcpus) / ACTICLOUD_OVERSUBSCRIPTION))
		nr_vcpus_host = host_state.vcpus_total
		free_vcpus = nr_vcpus_host - (nr_gold_vcpus + nr_silver_vcpus_ovs)

		LOG.info("Executing acticloud gold weigher for host %(host)s %(free_vcpus)d", {'host': hostname, 'free_vcpus': free_vcpus})

		"""Higher weights win."""
		return float(-free_vcpus)

class ActicloudNoisyWeigher(weights.BaseHostWeigher):
	def __init__(self):
		LOG.info("Hello from Noisy __init__")
		self.acticlouddb_client = ActiCloudDBClient()

	def _weigh_object(self, host_state, weight_properties):
		hostname = host_state.nodename
		nr_noisy = self.acticlouddb_client.get_nr_noisy_vms_by_hostname(hostname)
		LOG.info("Executing acticloud noisy weigher for host %(host)s %(nr_noisy)d", {'host': hostname, 'nr_gold': nr_noisy})
		"""Higher weights win."""
		return 0 if nr_noisy == None else float(-nr_noisy)

class ActicloudSensitiveWeigher(weights.BaseHostWeigher):
	def __init__(self):
		LOG.info("Hello from Sensitive __init__")
		self.acticlouddb_client = ActiCloudDBClient()

	def _weigh_object(self, host_state, weight_properties):
		hostname = host_state.nodename
		nr_sensitive = self.acticlouddb_client.get_nr_sensitive_vms_by_hostname(hostname)
		LOG.info("Executing acticloud sensitive weigher for host %(host)s %(nr_sensitive)d", {'host': hostname, 'nr_gold': nr_sensitive})
		"""Higher weights win."""
		return 0 if nr_sensitive == None else float(-nr_sensitive)


class ActicloudGoldServerIsolationWeigher(weights.BaseHostWeigher):
	"""
	Weighs lab hosts by their current number of instances.
	"""
	def _weigh_object(self, host_state, weight_properties):
		LOG.info("Executing ActicloudGoldServerIsolationWeigher for host %(host)s %(num_instances)d", {'host': host_state.host, 'num_instances': host_state.num_instances})
		"""Higher weights win."""
		return host_state.num_instances
