from anytree import Node,RenderTree,NodeMixin
from datetime import datetime
from collections import OrderedDict
import numpy as np
from Billing import * 
from anytree.exporter import DotExporter
import sys

lut_1 = 1.01
lut_2 = 1.03
lut_3 = 1.06
os_limit = 5

class Core(NodeMixin, object):
	def __init__(self, coreid = 0, slowdown = 1.0, parent=None, children=None):
		super(Core, self).__init__()
		self.id = coreid
		self.slowdown = slowdown    # float: Represents the relative slowdown of the core
		self.parent = parent
		if children:
			self.children = children

	@property
	def name(self):
		return str(self)

	def __repr__(self):
		return "C:" + str(self.id)

	@property
	def running_gold(self):
		return 1 in [x.is_gold for x in self.children]

	# core: Core -> int. Hops to the closest common ancestor
	def Distance(self, core):
		vector = zip(self.ancestors, core.ancestors)
		for i in range(len(vector))[::-1]:
			if vector[i][0] == vector[i][1]:
				return len(vector) - i

	# vcpus: List[Vcpu] -> float
	def oversubscription(self, vcpus = []):
		new_util = sum([vcpu.cpu_util for vcpu in vcpus])
		total_os = (sum([vm.cpu_util for vm in self.children]) + new_util) * self.slowdown
		return total_os if total_os > 1.0 else 1.0

	# new_vcpu: Vcpu -> float
	def goldScore(self, new_vcpu):
		gold_on_core = 1 in [vcpu.is_gold for vcpu in self.children]
		new_gold = new_vcpu.is_gold and len(self.children) > 0
		return np.power(-1.0, new_gold or gold_on_core)

class Vcpu(NodeMixin, object):
	def __init__(self, vm_id, vcpu_id = 0, cpu_util = 1.0, is_gold = 0, is_noisy = 0, \
				is_sensitive = 0, cost_function = 0, parent = None, children = None):
		super(Vcpu, self).__init__()
		self.id = vm_id			# 16-byte uu-id
		self.vcpu_id = vcpu_id	# int: vCPU identifier
		self.cpu_util = cpu_util
		self.is_gold = is_gold
		self.is_noisy = is_noisy
		self.is_sensitive = is_sensitive
		self.esd = 1.0
		if is_gold:
			self.cost_function = UserFacing(1)
		else:
			self.cost_function = UserFacing() if cost_function else Batch()
		self.parent = parent
		if children:
			self.children = children

	@property
	def name(self):
		ret = "vCPU " + str(self.vcpu_id) + ""
		return str(self)
	def __repr__(self):
		ret = "<vCPU " + str(self.vcpu_id) + " (" + self.id.split('-')[0] + ") "
		ret += "G|" if self.is_gold	else "S|"
		ret += "N|" if self.is_noisy else "Q|"
		ret += "S>" if self.is_sensitive else "I>"
		return ret

	# vcpu: Vcpu -> float
	def lut(self, vcpu):
		costs = [lut_1, lut_2, lut_2, lut_3]
		return costs[2 * vcpu.is_noisy + self.is_sensitive] if self.id != vcpu.id else 1.0

	# core: Core, vcpus: List[Vcpu], parent: Core (self.parent) ->float
	def interference(self, core, vcpus = [], parent = None):
		if not parent:
			parent = self.parent
		vcpu_children = [v for v in core.children if isinstance(v, Vcpu)]
		interf_from_new = sum([self.lut(vcpu) for vcpu in vcpus])
		interf_sum = sum([self.lut(vcpu) for vcpu in vcpu_children]) + interf_from_new
		interf_sum = interf_sum if interf_sum > 1.0 else 1.0
		nr_vms = float(len(vcpu_children) + len(vcpus))
		est_slowdown = interf_sum / nr_vms if nr_vms > 0 else 1.0
		distance = parent.Distance(core)
		scale = 1.0 / (2 ** (distance - 1.0))
		return est_slowdown ** scale if parent != core else 1.0

	# core: Core, vcpus: List[Vcpu], cur_esd: float -> float
	# Recalculates esd assuming vcpus run on core
	def recalculate_esd(self, core, vcpus, cur_esd = 0):
		if cur_esd == 0:
			cur_esd = self.esd
		new_esd = 1
		if core == self.parent:
			truncated_esd = cur_esd / core.oversubscription()
			new_esd = truncated_esd * core.oversubscription(vcpus)
		else:
			truncated_esd = cur_esd / self.interference(core)
			new_esd = truncated_esd * self.interference(core, vcpus)
		return new_esd

	def profit(self, sd = 0):
		return self.cost_function.cost(self.esd if sd == 0 else sd)

class VcpuBubble(Vcpu):
	def __init__(self, vm_id, vcpu_id = 0, cpu_util = 1.0, is_gold = 0, is_noisy = 0, \
				is_sensitive = 0, cost_function = 0, parent = None, children = None):
		super(VcpuBubble, self).__init__(vm_id, vcpu_id, cpu_util, is_gold, is_noisy, \
				is_sensitive, cost_function, parent, children)

	@property
	def name(self):
		ret = "vCPU " + str(self.vcpu_id) + " (bubble)"
		return str(self)
	def __repr__(self):
		ret = "<vCPU " + str(self.vcpu_id) + " (" + self.id.split('-')[0] + ") [BUBBLE] "
		ret += "G|" if self.is_gold	else "S|"
		ret += "N|" if self.is_noisy else "Q|"
		ret += "S>" if self.is_sensitive else "I>"
		return ret

	def lut(self, vcpu):
		return 1.0

	def interference(self, core, vcpus = [], parent = None):
		return 1.0

	def recalculate_esd(self, core, vcpus, cur_esd = 0):
		return 1.0

class Vm(object):
	def __init__(self, vmid = 'null', vcpus = 1, cpu_util = 1.0, is_gold = 0, is_noisy = 0, \
				is_sensitive = 0, cost_func = 0, openstack_instance = None):
		super(Vm, self).__init__()
		self.id = vmid			# 16-byte hash
		self.vcpus = list()		# List[Vcpu] List of vCPUs related to this VM
		for i in range(vcpus):
			self.vcpus.append(Vcpu(vmid, i, cpu_util, is_gold, is_noisy, is_sensitive, cost_func))
		self.openstack = openstack_instance		# VM's Openstack instance
		self.moves = 0			# int: Number of moves while in this compute node
		self.interference_cnt = 0	# int: Counter for ignoring interference before the limit
		self.last_move = datetime.now()	# datetime: Moment of the last move of the VM
		self.is_gold = is_gold
		self.is_noisy = is_noisy
		self.is_sensitive = is_sensitive
		self.bubble = []

	def __repr__(self):
		if (len(self.vcpus) <= 0):
			print "ERROR: len(self.vcpus) = %d" % len(self.vcpus)
			sys.exit(1)
		vcpu = self.vcpus[0]
		ret = "<VM " + self.id.split('-')[0] + " : " + str(len(self.vcpus)) + " vCPUs | "
		ret += "User  |" if isinstance(vcpu.cost_function, UserFacing) else "Batch |"
		ret += "G|" if vcpu.is_gold else "S|"
		ret += "N|" if vcpu.is_noisy else "Q|"
		ret += "S>" if vcpu.is_sensitive else "I>"
		return ret

class Socket(NodeMixin):
	def __init__(self, socket_id, parent = None, children = None):
		super(Socket, self).__init__()
		self.id = socket_id
		self.empty = True
		self.reserved_for_gold = False
		self.parent = parent
		if children:
			self.children = children

	def __repr__(self):
		return "Socket " + str(self.id)

class BaseSystem(object):
	def __init__(self, shape, name):
		self.shape = shape	# List[int]: List representing the system's isolation domains
		self.name = name
		self.tree = Node(name)	# Node: Root of the system's tree
		self.vms = OrderedDict()	# (Key: VM-uuid, Value: Vm class instances)
		self.server_overload = False
		pass

	def __repr__(self):
		return str(RenderTree(self.tree))

	def placeVM(self, vm):
		pass

	def deleteVM(self, vmid):
		pass
