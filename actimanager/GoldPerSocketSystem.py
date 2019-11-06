from System import *

class GoldPerSocketSystem(BaseSystem):
	def __init__(self, shape, name):
		super(GoldPerSocketSystem, self).__init__(shape, name)
		self.GenerateTree([shape[0], shape[-1]], self.tree)
		self.cores = self.tree.leaves
		self.sockets = self.tree.children

	def __repr__(self):
		return str(RenderTree(self.tree))

	def GenerateTree(self, shape, node):
		for i in range(shape[0]):
			if len(shape) == 1:
				cpu = Core(len([x for x in self.tree.leaves if isinstance(x,Core)]), parent=node)
			else:
				intermediate = Socket(len(self.tree.children), parent=node)
				self.GenerateTree(shape[1:], intermediate)

	def check_fit(self, vcpus):
		cores = 0
		if vcpus > len(self.cores):
			return False
		for socket in self.sockets:
			if socket.empty:
				cores += len(socket.children)
				if cores >= vcpus:
					return True
		return False

	def place_in_sockets(self, vcpus):
		pcpu_mapping = list()
		for socket in self.sockets:
			if socket.empty:
				socket.reserved_for_gold = True
				socket.empty = False
				if len(vcpus) > len(socket.children): 
					subset = vcpus[0 : len(socket.children)]
					vcpus = vcpus[len(socket.children):]
					for (vcpu, core) in zip(subset, list(socket.children)):
						vcpu.parent = core
						pcpu_mapping.append(core.id)
				else:
					dst = socket.children[0:len(vcpus)]
					for (vcpu, core) in zip(vcpus, list(dst)):
						vcpu.parent = core
						pcpu_mapping.append(core.id)
					return pcpu_mapping

	def repin_silvers(self):
		moves = list()
		silver_target = [core.id for core in self.cores if not core.parent.reserved_for_gold]
		for vm in [v for v in self.vms.values() if not v.is_gold]:
			for vcpu in vm.vcpus:
				vcpu.parent = self.cores[silver_target[0]]
			moves.append((vm, silver_target))
		return moves

	def placeVM_Kernel(self, vm):
		moves = list()
		pcpu_mapping = list()
		vcpus = vm.vcpus
		if vm.is_gold: # Gold VM Handler
			if not self.check_fit(len(vcpus)):
				return []
			moves.append((vm, self.place_in_sockets(vcpus)))
			moves += self.repin_silvers()
		else: # Silver VM Handler
			if len([s for s in self.sockets if not s.empty and not s.reserved_for_gold]) == 0:
				empty_sockets = [s for s in self.sockets if s.empty]
				if len(empty_sockets):
					silver_socket = empty_sockets[-1]
					silver_socket.empty = False
				else:
					return []
			pcpu_mapping = [core.id for core in self.cores if not core.parent.reserved_for_gold]
			for vcpu in vm.vcpus:
				vcpu.parent = self.cores[pcpu_mapping[0]]
			moves.append((vm, pcpu_mapping))
		if vm.id not in self.vms:
			self.vms[vm.id] = vm
		return moves

	def placeVM(self, vm):
		rollback = dict()
		for v in self.vms.values():
			for vcpu in v.vcpus:
				rollback[vcpu] = vcpu.parent
		moves = self.placeVM_Kernel(vm)
		if moves == []:
			for vcpu in rollback:
				vcpu.parent = rollback[vcpu]
			for vcpu in vm.vcpus:
				vcpu.parent = None
			return []
		return moves

	def deleteVM(self, vmid):
		vm = self.vms[vmid]
		for vcpu in vm.vcpus:
			socket = vcpu.ancestors[1]
			vcpu.parent = None
			if len(socket.children[0].children) == 0:
				socket.empty = True
				socket.reserved_for_gold = False
			del vcpu
		del self.vms[vmid]
		return
