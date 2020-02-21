import json
import paramiko
import configparser
import ast
import logging, time, operator, threading, pika, math, signal, sys
sys.path.append('.')
sys.path.append('../common/')
from openstack_client import OpenstackClient
from Internal import DecisionMaker, InformationAggregator

config = configparser.ConfigParser()
config.read("../actimanager_uvisor/actimanager.cfg")
CFG_SECTION = "uvisor_hypervisor"

def IS_UVISOR_DN1_VM(uvisor_vm):
	return str(uvisor_vm) == "dn1"

class uvisorOpenstackClient(OpenstackClient):
	def live_migrate_vm(self, vm_uuid, dst):
		return -1

	def get_hypervisors(self):
		return self.nova.hypervisors.list()

	def get_instances_by_hypervisor(self, hypervisor):
		#return self.nova.servers.list(search_opts={'hypervisor_hostname': hypervisor})
		return self.nova.hypervisors.list()

	def get_instance_by_vm_id(self, vm_id):
		return self.nova.servers.get(vm_id)
		

class SSHObj():
	def __init__(self):
		self.CONTROLLER_IP = config.get(CFG_SECTION, "controller_ip")
		self.CONTROLLER_SSH_USER = config.get(CFG_SECTION, "controller_ssh_user")
		self.LOCAL_PORT = config.get(CFG_SECTION, "local_port")

	def ssh_exec(self, command, has_output):
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		
		ssh.connect(self.CONTROLLER_IP, username=self.CONTROLLER_SSH_USER)
		ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)

		if (has_output):
			output = ssh_stdout.read().decode('ascii').strip("\n")
			res = ast.literal_eval(output) 
			ssh.close()
			return res
		else: 
			ssh.close()
			return 0

	def _ssh_exec(self, command):
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		
		ssh.connect(self.CONTROLLER_IP, username=self.CONTROLLER_SSH_USER)
		ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)

#		res = ast.literal_eval(output) 
		output = ssh_stdout.read().decode('ascii').strip("\n")

		ssh.close()

		return output


class uvisorExecutor():
	def __init__(self):
		self.openstack_client = uvisorOpenstackClient()
		self.PCPUS_OFFSET = config.getint(CFG_SECTION, "pcpus_offset")
		self.NPCPUS = config.get(CFG_SECTION, "npcpus")

	def exec_rest(self, path, is_get, put_command):
		ssh = SSHObj();
		if (is_get):
			ssh_command = "curl --silent -X GET http://localhost:" + ssh.LOCAL_PORT + "/mvNode/" + path
			return ssh.ssh_exec(ssh_command, 1)
		else:
			ssh_command = "\"curl --silent -d " + "'" + put_command + "'" + " -X PUT http://localhost:" + ssh.LOCAL_PORT + "/mvNode/" + path + "\""
			return ssh.ssh_exec(ssh_command, 0)
		
	def exec_osd(self, command):
		ssh = SSHObj();
		ssh_command = "osd " + command
		return ssh._ssh_exec(ssh_command)

	def exec_mvctl(self, command):
		ssh = SSHObj();
		ssh_command = "/virtx/bin/mvctl --mvmac 0cc47a77f9af " + command
		return ssh._ssh_exec(ssh_command)

	def get_uvisor_hypervisors(self):
		res = ex.exec_osd("get_nodes")
		one_line_ids = ""
		for line in res.splitlines():
			if ("id=" in line and not ("_") in line):
				one_line_ids += line.replace(" ", "") + "="
		splitted_ids = one_line_ids.split("=")
		ids = []
		for i in range(len(splitted_ids)):
			if (i % 2):
				ids.append(splitted_ids[i])
		return ids

	def get_hypervisors(self):
		return self.openstack_client.get_hypervisors()

	def get_openstack_vm_id(self, uvisor_vm):
		# uvisor_vm is something like dn19
		res = self.exec_osd("get_instance --id=" + uvisor_vm[2:])
	
		for line in res.splitlines():
			if ("name=" in line and not "domain" in line and not "host" in line):
				return line.strip().split('=')[1]

		#return res[7].strip().split('=')[1]
		return -1

	def get_all_uvisor_vms(self):
		res = self.exec_osd("get_instances --filter=id")

		vms = []
		for line in res.splitlines():
			if ("ids=" in line):
				line_vms = line.strip().split('=')[1].split(',')
				for vm in line_vms:
					vms.append("dn" + vm)
				
				return vms

	def get_vms_by_hypervisor(self, hypervisor_id):
		data = self.exec_rest(hypervisor_id + "/VM/", 1, "") 

		vms = []

		for key in data:
			if key.startswith("dn") and not "dn1" == key:
				vm = self.get_openstack_vm_id(key)
				#FIXME: openstack_client search by id
				vms.append(self.openstack_client.get_instance_by_vm_id(vm))
				#vms.append(vm)

		return vms

	def get_uvisor_vm_from_openstack_vm(self, openstack_vm):
		all_vms = self.get_all_uvisor_vms()
		
		for uvisor_vm in all_vms:
			if IS_UVISOR_DN1_VM(uvisor_vm):
				continue
			aa = self.get_openstack_vm_id(uvisor_vm)
			if openstack_vm.id == self.get_openstack_vm_id(uvisor_vm):
				return uvisor_vm

		return -1

	def get_uvisor_domid(self, uvisor_vm):
		hypervisor = self.get_hypervisor_from_uvisor_vm(uvisor_vm)
		data = self.exec_rest(str(hypervisor.hypervisor_hostname) + "/VM/" + str(uvisor_vm), 1, "") 
		domid = data.get(uvisor_vm).get("domid")
		return domid

	def get_hypervisor_from_uvisor_vm(self, uvisor_vm):
		hypervisors = self.get_hypervisors()

		for hypervisor in hypervisors:
			data = self.exec_rest(str(hypervisor.hypervisor_hostname) + "/VM/", 1, "") 
			if data.get(uvisor_vm) != None:
				return hypervisor

		return -1

	def pin_vcpu_rest(self, vm, vcpu, pcpu):
		openstack_vm = vm.id
		uvisor_vm = self.get_uvisor_vm_from_openstack_vm(openstack_vm)
		hypervisor = self.get_hypervisor_from_uvisor_vm(uvisor_vm)
		res = self.exec_rest(str(hypervisor.hypervisor_hostname) + "/VM/" + str(uvisor_vm), 0, "vcpupin " + str(vcpu) + " " + str(pcpu))
		return True

	def pin_vcpu(self, openstack_vm, vcpu, pcpu):
		#openstack_vm = vm.id
		uvisor_vm = self.get_uvisor_vm_from_openstack_vm(openstack_vm)
		domain_id = self.get_uvisor_domid(uvisor_vm)

		pcpu += self.PCPUS_OFFSET
		res = self.exec_mvctl("--vcpu-pin -d " + str(domain_id) + " -v " + str(vcpu) + " -c " + str(pcpu))
		return (not "failed" in res)

	def get_vcpu_pin_info(self, openstack_vm):
		#openstack_vm = vm.id
		uvisor_vm = self.get_uvisor_vm_from_openstack_vm(openstack_vm)
		domain_id = self.get_uvisor_domid(uvisor_vm)

		res = self.exec_mvctl("--vcpuinfo " + str(domain_id))

		npcpus = int(self.NPCPUS) - self.PCPUS_OFFSET + 1
		pcpus = [ True for i in range(npcpus) ]
		if not "all" in str(res):
			pcpus = [ False for i in range(npcpus) ]
			pcpus[int(res.split(" ")[2]) - self.PCPUS_OFFSET] = True

		return pcpus
		
class uvisorDecisionMaker(DecisionMaker):
	def __init__(self, information_aggregator, hostname):
		self.ex = uvisorExecutor()
		DecisionMaker.__init__(self, information_aggregator, hostname)

	def pin_vcpu(self, vm, vcpu, pcpu):
		return self.ex.pin_vcpu(vm, vcpu, pcpu)		

class uvisorInformationAggregator(InformationAggregator):
	def __init__(self, compute_node_name, system_type):
		self.ex = uvisorExecutor()
		InformationAggregator.__init__(self, compute_node_name, system_type)

	def getVMVcpuMapping(self, vm):
		#FIXME: return the same list as getVMVcpuMapping()
		return self.ex.get_vcpu_pin_info(vm)

	def getServerListByComputeNode(self, hypervisor_id):
		return self.ex.get_vms_by_hypervisor(hypervisor_id)

if __name__ == '__main__':
	ex = uvisorExecutor()
#	osc = uvisorOpenstackClient()

	#print ex.pin_vcpu_rest("abd992b4-4e61-4e5d-a178-80358864ad69", 0, 8)
#	print ex.pin_vcpu("abd992b4-4e61-4e5d-a178-80358864ad69", 0, 8)
	#print ex.get_vms_by_hypervisor("7a77f9af")
	print ex.get_vms_by_hypervisor("7a77f9af")
#	print ex.get_vms_by_hypervisor("6b6d33f0")

#	print ex.get_vcpu_pin_info("abd992b4-4e61-4e5d-a178-80358864ad69")
