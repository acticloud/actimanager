from System import *

class GoldNotOversubscribedSystem(BaseSystem):
	def __init__(self, shape, name):
		super(GoldNotOversubscribedSystem, self).__init__(shape, name)
		self.GenerateTree([np.prod(self.shape)], self.tree)
		self.cores = self.tree.leaves

	def __repr__(self):
		return str(RenderTree(self.tree))

	def GenerateTree(self, shape, node):
		for i in range(shape[0]):
			core = Core(len([x for x in self.tree.leaves if isinstance(x, Core)]), parent=node)

	def repin_silvers(self):
		moves = list()
		s_target = [core.id for core in self.cores if not core.running_gold]
		for vm in [v for v in self.vms.values() if not v.is_gold]:
			for vcpu in vm.vcpus:
				vcpu.parent = self.cores[s_target[0]]
			moves.append((vm, s_target))
		return moves

	def placeVM_Kernel(self, vm):
		moves = list()
		pcpu_mapping = list()
		vcpus = vm.vcpus
		if vm.is_gold: # Gold VM Handler
			empty_cores = [core for core in self.cores if len(core.children) == 0]
			if len(empty_cores) < len(vcpus):
				return []
			dst = empty_cores[0: len(vcpus)]
			for (vcpu, core) in zip(vcpus, list(dst)):
				vcpu.parent = core
				pcpu_mapping.append(core.id)
			moves.append((vm, pcpu_mapping))
			moves += self.repin_silvers()
		else: # Silver VM Handler
			pcpu_mapping = [core.id for core in self.cores if not core.running_gold]
			for vcpu in vm.vcpus:
				vcpu.parent = self.cores[pcpu_mapping[0]]
			moves.append((vm, pcpu_mapping))
		if vm.id not in self.vms:
			self.vms[vm.id] = vm
		return moves

	def placeVM(self, vm):
		if vm.id in self.vms:
			return []
		rollback = dict()
		for v in self.vms.values():
			for vcpu in v.vcpus:
				rollback[vcpu] = vcpu.parent
		moves = self.placeVM_Kernel(vm)
		if moves == []:
			for vcpu in rollback:
				if vcpu.parent != rollback[vcpu]:
					vcpu.parent = rollback[vcpu]
			for vcpu in vm.vcpus:
				vcpu.parent = None
			return []
		return moves

	def deleteVM(self, vmid):
		vm = self.vms[vmid]
		for vcpu in vm.vcpus:
			vcpu.parent = None
			del vcpu
		del self.vms[vmid]
		if vm.is_gold:
			return self.repin_silvers()
