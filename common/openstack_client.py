## Basic python packages
import sys, imp, logging, time

## Openstack packages
from keystoneauth1.identity import v2
from keystoneauth1 import session, loading
from novaclient import client as novaclient
from glanceclient import client as glanceclient

## Openstack credentials stored in a common file
credentials = imp.load_source('credentials', '../common/credentials.py')

class OpenstackClient():
	def __init__(self):
		## Setup logging facility
		self.logger = logging.getLogger(__name__)

		## Nova client
		## NOTE(jimsiak): Version 2.24 for the live_migrate_force_complete() function
		creds = credentials.get_nova_creds()
		self.nova = novaclient.Client("2.24", **creds)

		## Glance client
		loader = loading.get_plugin_loader('password')
		auth = loader.load_from_options(auth_url=creds['auth_url'],
		                                username=creds['username'],
		                                password=creds['password'],
		                                user_domain_name=creds['user_domain_name'],
		                                project_domain_name=creds['project_domain_name'],
		                                project_name=creds['project_name'])
		self.glance = glanceclient.Client('2', session=session.Session(auth=auth))

	def get_hypervisors(self):
		return self.nova.hypervisors.list()

	def get_images(self):
		return list(self.glance.images.list())

	def get_flavors(self):
		return self.nova.flavors.list()
	def get_flavor_by_name(self, flavor_name):
		flavors = self.get_flavors()
		for flavor in flavors:
			if flavor_name in flavor.name:
				return flavor
		return None
	def get_flavor_by_id(self, flavor_id):
		flavors = self.get_flavors()
		for flavor in flavors:
			if flavor_id in flavor.id:
				return flavor
		return None

	def get_vms(self):
		return self.nova.servers.list()
	def get_vms_by_hostname(self, hostname):
		return self.nova.servers.list(search_opts={'host': hostname})
	def get_vm(self, vm):
		try:
			return self.nova.servers.get(vm)
		except novaclient.exceptions.NotFound:
			return None
	def get_vm_current_host(self, vm_uuid):
		vm = self.get_vm(vm_uuid)
		if not vm:
			return None
		return getattr(vm, 'OS-EXT-SRV-ATTR:host')

	def delete_all_vms(self):
		for vm in self.get_vms():
			self.nova.servers.delete(vm)
	def delete_existing_vms(self, prefix=""):
		vms = self.get_vms()
		for vm in vms:
			if prefix in vm.name:
				self.logger.info("Deleting VM with name: %s (status: %s)" % (vm.name, vm.status))
				self.nova.servers.delete(vm)
		return len(vms)
	
	def get_data_center_vcpus(self):
		vcpus_avail = 0
		vcpus_used = 0
		for h in self.get_hypervisors():
			if not (h.status == "enabled" and h.state == "up"):
				continue
			vcpus_avail += h.vcpus
			vcpus_used += h.vcpus_used
		return [vcpus_avail, vcpus_used]

	def live_migrate_vm(self, vm_uuid, dst):
		self.logger.info("Live Migrating VM %s", vm_uuid)
		try:
			ret = self.nova.servers.live_migrate(host=dst, server=vm_uuid,
			                               block_migration=False, disk_over_commit=False)
		except novaclient.exceptions.Conflict:
			## VM was in a state (e.g., "migrating")
			self.logger.error("Could not migrate VM %s", vm_uuid)
			return
		time.sleep(10) # Let some time pass for the migration to be visible in the migration list

		## Now let's make sure that the VM will be migrated
		for i in range(10):
			pending_migration_list = self.nova.migrations.list(instance_uuid=vm_uuid)
			if (len(pending_migration_list) == 0 or pending_migration_list[0].status == "completed"):
				self.logger.info("VM %s Successfully migrated to %s", vm_uuid, dst)
				return

			self.logger.info("Migration of VM %s still pending (status: %s)... Sleeping for 10 seconds...",
			                 vm_uuid, pending_migration_list[0].status)
			time.sleep(10)

		pending_migration_list = self.nova.migrations.list(instance_uuid=vm_uuid)
		if (len(pending_migration_list) == 0 or pending_migration_list[0].status == "completed"):
			self.logger.info("VM %s Successfully migrated to %s", vm_uuid, dst)
		else:
			migration_id = pending_migration_list[0].id
			self.logger.info("Migration (id: %s) of VM %s failed to converge. Forcing the migration.",
			                 migration_id, vm_uuid)
			self.nova.server_migrations.live_migrate_force_complete(vm_uuid, migration_id)
			self.logger.info("VM %s Successfully migrated (forced) to %s", vm_uuid, dst)

	def pause_vm(self, vm_uuid):
		self.nova.servers.pause(server=vm_uuid)

	def unpause_vm(self, vm_uuid):
		self.nova.servers.unpause(server=vm_uuid)
