#!/usr/bin/env python

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import socket, pickle, time, sys, random, datetime
import imp
openstack_client = imp.load_source('openstack_client', '../common/openstack_client.py')
libvirt_client = imp.load_source('libvirt_client', '../common/libvirt_client.py')

BIG_WIDTH = 1
LITTLE_WIDTH = 1

HOSTS = ['acticloud1', 'acticloud2', 'acticloud3', 'acticloud4']
NUM_CPUS = 20

ost_client = openstack_client.OpenstackClient()
flavors = ost_client.get_flavors()

def get_vm_tag_str(vm):
	flavor_id = vm.flavor['id']
	flavor_name = None
	for f in flavors:
		if f.id == flavor_id:
			flavor_name = f.name
	if "gold" in flavor_name:
		vm_tag_str = "gold"
	elif "silver" in flavor_name:
		vm_tag_str = "silver"
	return vm_tag_str

def getVMVcpuMapping(hostname, vm):
	libvirt_instance_name = getattr(vm, 'OS-EXT-SRV-ATTR:instance_name')
	try:
		with libvirt_client.LibVirtConnection(hostname, "qemu+ssh") as libvconn:
			libvinstance = libvirt_client.LibVirtInstance(libvconn, str(libvirt_instance_name))
			vcpu_mappings = list(libvinstance.get_instance_mapping())
	except:
		return None
	total_mapping = np.array(vcpu_mappings[0])
	for m in vcpu_mappings[1:]:
		total_mapping = total_mapping | np.array(m)
	return list(total_mapping)

while 1:
	for hostname in HOSTS:
		nr_gold_vcpus = 0
		nr_silver_vcpus = 0
		ax = plt.subplot(111)
		x = np.arange(1, NUM_CPUS+1)
		bottoms = np.zeros(NUM_CPUS)

		vms = ost_client.get_vms_by_hostname(hostname)
		for vm in reversed(vms):
			if vm.status != "ACTIVE":
				continue

			vm_vcpus = ost_client.get_flavor_by_id(vm.flavor['id']).vcpus
			vm_tag_str = get_vm_tag_str(vm)
			vm_mapping = getVMVcpuMapping(hostname, vm)

			if vm_mapping == None:
				continue

			if vm_tag_str == "gold":
				nr_gold_vcpus += vm_vcpus
			elif vm_tag_str == "silver":
				nr_silver_vcpus += vm_vcpus

			colors = []
			vcpus_assigned_color = 0
			for val in vm_mapping:
				if not val:
					colors.append("white")
				elif vcpus_assigned_color >= vm_vcpus:
					colors.append("gray")
				else:
					colors.append(vm_tag_str)
					vcpus_assigned_color += 1

			for cpu in range(len(vm_mapping)):
				ax.bar([x[cpu]], [1.0], bottom=[bottoms[cpu]], color=colors[cpu])
			bottoms += 1.2

		ax.set_ylim(0, 30)
		ax.set_xlim(-0.5, NUM_CPUS + 1.5)
		plt.xticks(np.arange(1, NUM_CPUS + 0.5), np.arange(NUM_CPUS))
		plt.yticks([])
		time_updated = datetime.datetime.utcnow().strftime("%Y-%m-%d.%X")
		title = "VCPUS: %d GOLD and %d SILVER (%.2f per pcpu)\nLast Update: %s" % \
		          (nr_gold_vcpus, nr_silver_vcpus, \
		           float(nr_silver_vcpus) / ((NUM_CPUS - nr_gold_vcpus) or 1), \
		           time_updated)
		plt.title(title)
		
		plt.savefig("images/output-"+hostname+".png", bbox_inches = 'tight')
		plt.close()

	time.sleep(2)
