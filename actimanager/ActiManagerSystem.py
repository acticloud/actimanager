import logging
from Billing import * 
from System import *

report_dir = "/root/ypap/reports/"

class ActiManagerSystem(BaseSystem):
	def __init__(self, shape, name):
		super(ActiManagerSystem, self).__init__(shape, name)
		self.logger = logging.getLogger(self.__class__.__name__)
		self.GenerateTree(self.shape, self.tree)
		self.cores = self.tree.leaves
		self.socket_cost = SocketCost(len(self.tree.children), ServerCost(len(self.cores)).cost)
		self.cur_profit = 0.0
		self.report_file = open(report_dir + name + "_report.txt", "a")
		self.report_file.close()

	# shape: List[int], node: Node -> void. Constructs the system's tree according to shape
	def GenerateTree(self, shape, node):
		for i in range(shape[0]):
			if len(shape) == 1:
				core = Core(len([x for x in self.tree.leaves if isinstance(x, Core)]), parent=node)
			else:
				child = Node("L" + str(len(shape)) + "." + \
						str(len([x for x in self.tree.leaves if isinstance(x,Core)])), parent=node)
				self.GenerateTree(shape[1:], child)

	def repin_silvers(self):
		pass

	# leaf: Core -> float. Cost to turn on an empty socket
	def TurnOnCost(self, leaf):
		dist = leaf.depth - 1
		for core in self.cores:
			if (len(core.children)):
				tmp = core.Distance(leaf) - 1
				if dist > tmp:
					dist = tmp
		if dist == leaf.depth - 1:
			return self.socket_cost.cost
		return 0

	# vcpu: Vcpu, core: Core -> (float, float). Calculate money and esd for vcpu if placed on core
	def core_profit_calculate(self, vcpu, core):
		if core.goldScore(vcpu) < 0:
			return (0, -1)
		else:
			money = 0.0
			new_esd = core.oversubscription([vcpu])
			for core_other in self.cores:
				new_esd *= vcpu.interference(core_other, [], core)
				for vm in core_other.children:
					money += vm.profit(vm.recalculate_esd(core, [vcpu]))
			money += vcpu.profit(new_esd)
			if vcpu.id not in self.vms: # New VM
				money -= self.TurnOnCost(core)
			return (money, new_esd)

	# vcpu: Vcpu -> (List[float], List[float])
	def profit_calculate(self, vcpu):
		money = list()
		esd = list()
		for core_to_run in self.cores:
			(new_money, new_esd) = self.core_profit_calculate(vcpu, core_to_run)
			money.append(new_money)
			esd.append(new_esd)
		return (money, esd)

	# scores: (List[float], List[float]), vcpu: Vcpu, excluded: List[Core] -> (int, float, float)
	def silver_dst_decide(self, scores, vcpu, excluded = [], added_toc = False):
		(money, esd) = scores
		valid_scores = dict()
		for i, x in enumerate(money):
			if (esd[i] > 0) and (self.cores[i] not in excluded) \
			                and (len(self.cores[i].children) < os_limit):
				valid_scores[i] = x
		if len(valid_scores.values()) == 0:
			self.logger.error("Failed to pin VM, valid_scores is [] for some reason")
			return (-1, 0, 0)
		max_score_cores = [i for i,x in enumerate(money) if x == max(valid_scores.values()) \
															and i in valid_scores]
		if len(max_score_cores) == 1:
			targets = max_score_cores
		else:
			nr_children = [(len(c.children), c.id) for c in self.cores if c.id in max_score_cores]
			min_children =	filter(lambda x: x[0] == min(nr_children, key = lambda y: y[0])[0], \
							nr_children)
			targets = [x[1] for x in min_children]
		if targets == []:
			self.logger.error("Failed to pin VM due to oversubscription limit violation")
			return (-1, 0, 0)
		dst = targets[0]
		if money[dst] < self.cur_profit:
			if not added_toc:
				socket_cost = [self.TurnOnCost(core) for core in self.cores]
				if max(socket_cost) > 0:
					money = [sum(x) for x in zip(money, socket_cost)]
					return self.silver_dst_decide((money, esd), vcpu, excluded, True)
		return (dst, money[dst], esd[dst])

	# vm: Vcpu, target: Core
	def update_esd(self, vm, target):
		for core in self.cores:
			for vcpu in [v for v in core.children if isinstance(v, Vcpu)]:
				vcpu.esd = vcpu.recalculate_esd(target, [vm])

	# vcpu: Vcpu
	def calculate_esd(self, vcpu):
		if vcpu.parent == None:
			return 1.0
		esd = vcpu.parent.oversubscription()
		for c in self.cores:
			esd *= vcpu.interference(c)
		return esd

	def calculate_total_money(self):
		money = 0.0
		for c in self.cores:
			for vcpu in [v for v in c.children if isinstance(v, Vcpu)]:
				money += vcpu.profit(self.calculate_esd(vcpu))			
		return money

	# m: int, excluded: List[Core] -> List[(Core,..)] 
	def search_for_contiguous_cores(self, m, excluded = []):
		subset = [x for x in self.cores if x not in excluded]
		found = OrderedDict()
		for core in subset:
			start_core = core
			try:
				end_core = subset[subset.index(start_core) + m - 1]
			except:
				break
			distance = start_core.Distance(end_core)
			group = tuple(subset[subset.index(start_core) : subset.index(end_core) + 1])
			nr_parents = len(list(set([node.parent for node in group])))
			silver_vms = 0
			gold_vms = 0
			for c in group:
				silver_vms += len([vm for vm in c.children if vm.is_gold == 0])
				gold_vms += len([vm for vm in c.children if vm.is_gold == 1])
			found[group] = (distance, gold_vms, silver_vms, nr_parents)
		# Filter the found groups
		for num_gold in sorted(list(set(map(lambda x: x[1][1], found.items())))):
			for distance in sorted(list(set(map(lambda x: x[1][0], found.items())))):
				for nr_parents in sorted(list(set(map(lambda x: x[1][3], found.items())))):
					slots = [group for group in found.items() \
								if group[1][0] == distance and \
									group[1][1] == num_gold and \
									group[1][3] == nr_parents]
					if slots != []:
						return [group[0] for group in slots \
								if group[1][2] == min(map(lambda x: x[1][2], slots))]

	# groups: List[(Core,..)], vcpus: List[Vcpu], excluded: List[Core] -> (Core,..)
	def gold_dst_decide(self, groups_input, vcpus, excluded = []):
		groups = list()
		for group in groups_input:
			(silver_moved, gold_moved) = (0,0)
			for core in group:
				silver_moved += len([v for v in core.children if not v.is_gold])
				gold_moved += len([v for v in core.children if v.is_gold])
			available_cores = [c for c in self.cores if c not in group]
			(silver_on_available_cores, gold_on_available_cores) = (0,0)
			for core in available_cores:
				silver_on_available_cores += len([v for v in core.children if not v.is_gold])
				gold_on_available_cores += len([v for v in core.children if v.is_gold])
			if gold_moved + gold_on_available_cores + (silver_moved + silver_on_available_cores) / (os_limit - 1) <= len(available_cores):
				groups.append(group)
		if len(groups) == 0:
			return ()
		if len(groups) == 1:
			return groups[0]
		previous_state = OrderedDict()
		previous_profit = self.cur_profit
		for vm in self.vms.values():
			for vcpu in vm.vcpus + vm.bubble:
				previous_state[vcpu] = (vcpu.parent, vcpu.esd)
		group_scores = OrderedDict()
		for group in groups:
			for core in group:
				for vcpu in core.children:
					moves = self.placeVM_Kernel(vcpu, list(set(excluded + list(group))), True)
			money = 0
			for (vcpu, core) in zip(vcpus, group):
				if isinstance(vcpu, Vcpu):
					money += self.core_profit_calculate(vcpu, core)[0]
			group_scores[group] = money
			self.cur_profit = previous_profit # Revert State
			for vcpu in previous_state:
				(vcpu.parent, vcpu.esd) = previous_state[vcpu]
		(dst, money) = max(group_scores.items(), key = lambda x: x[1])
		if money < self.cur_profit:
			for group in groups:
				for c in group:
					group_scores[group] += self.TurnOnCost(c)
			dst = max(group_scores.items(), key = lambda x: x[1])[0]
		return dst

	# group: (Core,..), excluded: List[Core] -> List[(Vm, core_id: List[int])]
	def make_room(self, group, excluded = []):
		excluded = list(group)
		moves = list()
		moved_vms = list()
		for core in group:
			for vcpu in core.children:
				if self.vms[vcpu.id] not in moved_vms:
					moved_vms.append(self.vms[vcpu.id])
		for core in group:
			for vcpu in core.children:
				vm = self.vms[vcpu.id]
				target = self.placeVM_Kernel(vcpu, excluded, True)
				if target == []:
					return []
		for vm in moved_vms:
			moves.append((vm, [v.parent.id for v in vm.vcpus]))
		return moves

	# vm_info: Vm/Vcpu, excluded: List[Core] -> List[(Vm, core_id: List[int])]
	def placeVM_Kernel(self, vm_info, excluded = [], simulate = False):
		vm = vm_info if isinstance(vm_info, Vm) else self.vms[vm_info.id]
		vcpus = list()
		if isinstance(vm_info, Vm): # Path for directly placing a silver vm
			if vm.id in self.vms and not vm.is_gold:
				for vcpu in vm.vcpus:
					if vcpu.parent not in excluded:
						excluded.append(vcpu.parent)
			vcpus = vm.vcpus + vm.bubble
		elif isinstance(vm_info, Vcpu): # Path if called by make_room
			vcpus = [vm_info]
		if vm_info.id in self.vms:
			self.removeVM(vm_info)
		moves = list()
		pcpu_mapping = list()
		if vm.is_gold == 1: # Gold VM Handler
			groups = self.search_for_contiguous_cores(len(vcpus), excluded)
			dst = self.gold_dst_decide(groups, vcpus)
			if not dst:
				return []
			moves += self.make_room(dst, excluded)
			for (vcpu, core) in zip(vcpus, list(dst)):
				(_, vcpu.esd) = self.core_profit_calculate(vcpu, core)
				self.update_esd(vcpu,core)
				vcpu.parent = core
				if isinstance(vcpu, Vcpu):
					pcpu_mapping.append(core.id)
		else: # Silver VM Handler
			for vcpu in vcpus:
				scores = self.profit_calculate(vcpu)
				(dst, _, vcpu.esd) = \
					self.silver_dst_decide(scores, vcpu, excluded, False)
				if dst == -1:
					return []
				self.update_esd(vcpu, self.cores[dst])
				vcpu.parent = self.cores[dst]
				pcpu_mapping.append(dst)
		moves.append((vm, [v.parent.id for v in vm.vcpus]))
		if vm.id not in self.vms:
			self.vms[vm.id] = vm
		elif not simulate:
			vm.moves += 1
		self.cur_profit = self.calculate_total_money()
		return moves

	# vm: Vm -> List[(Vm, List[int])] 
	def placeVM(self, vm):
		new = vm.id not in self.vms
		rollback = dict()
		prev_money = self.cur_profit
		for v in self.vms.values():
			for vcpu in v.vcpus + v.bubble:
				rollback[vcpu] = (vcpu.parent, vcpu.esd)
		moves = self.placeVM_Kernel(vm, [], False)
		if moves == []:
			if new:
				for vcpu in rollback:
					(vcpu.parent, vcpu.esd) = rollback[vcpu]
				for vcpu in vm.vcpus:
					vcpu.parent = None
				if vm.id in self.vms:
					del self.vms[vm.id]
				self.cur_profit = prev_money
			return []
		self.server_overload = prev_money > self.cur_profit
		return moves

	# vm_info: Vm/Vcpu Removes the vcpu(s) from the system
	def removeVM(self, vm_info):
		vcpus = vm_info.vcpus + vm_info.bubble if isinstance(vm_info, Vm) else [vm_info]
		vmid = vcpus[0].id
		for vcpu in vcpus:
			vcpu.parent = None
		for c in self.cores:
			for vcpu in c.children:
				vcpu.esd = self.calculate_esd(vcpu)

	# vmid: uu-id -> List[(Vm, List[int])]. Deletes the VM from the system and the dictionary
	def deleteVM(self, vmid):
		vm = self.vms[vmid]
		self.removeVM(vm)
		for vcpu in vm.vcpus + vm.bubble:
			del vcpu
		del self.vms[vmid]
		self.cur_profit = self.calculate_total_money()


	def bubble_boost(self, vm):
		copy = vm.vcpus[0]
		vm.bubble = [VcpuBubble(vm.id, len(vm.vcpus) + i, 1.0, copy.is_gold, copy.is_noisy, \
					 copy.is_sensitive, copy.cost_function) for i in range(4 - len(vm.vcpus))]

	def rebalance(self):
		not_paying = list()
		for vm in self.vms.values():
			for v in vm.vcpus:
				if v.profit() == 0:
					not_paying.append(v)
		not_paying = sorted(not_paying, key = lambda x: x.is_gold)[::-1]
		rollback = dict()
		moves = list()
		for vcpu in not_paying:
			prev_money = self.cur_profit
			for vm in self.vms.values():
				for v in vm.vcpus:
					rollback[v] = (v.parent, v.esd)
			move = self.placeVM_Kernel(vcpu, [], False)
			if prev_money > self.cur_profit or vcpu.profit() == 0:
				for v in rollback:
					(v.parent, v.esd) = rollback[v]
				self.cur_profit = prev_money
			else:
				moves += move
			rollback = {}
		return moves

	def _get_gold_vms_not_paying(self):
		vms_not_paying = list()
		gold_vms = [ vm for vm in self.vms.values() if vm.is_gold ]
		for vm in gold_vms:
			not_paying_vcpus = [ vcpu for vcpu in vm.vcpus if vcpu.profit() == 0 ]
			if len(not_paying_vcpus) > 0:
				vms_not_paying.append(vm)
		return vms_not_paying

	def rebalance_global(self):
		## Get the gold vcpus that do not pay
		gold_vms_not_paying = self._get_gold_vms_not_paying()
		if len(gold_vms_not_paying) == 0:
			return

		self.logger.info("Going to do a global rebalance because there are gold VMs that do not pay: %s", gold_vms_not_paying)
		self.logger.info("Gold VMs that do not pay BEFORE the rebalance_global(): %d", len(gold_vms_not_paying))
		gold_vms = [ vm for vm in self.vms.values() if vm.is_gold == 1]
		gold_vms = sorted(gold_vms, key = lambda vm: len(vm.vcpus), reverse=True)

		silver_vms = [ vm for vm in self.vms.values() if vm.is_gold == 0 ]
		silver_vms = sorted(silver_vms, key = lambda vm: len(vm.vcpus), reverse=True)
		self.logger.debug("GOLD_VMS:", gold_vms)
		self.logger.debug("SILVER_VMS:", silver_vms)

		## FIXME we should remove all the VMs from the system here
		self.__init__(self.shape, self.name)

		## Perform the global rebalance by placing the VMs in order
		moves = list()
		not_placed_vms = list()
		for vm in gold_vms + silver_vms:
			previous_profit = self.cur_profit
			rollbacks = [ (v, v.parent, v.esd) for v in vm.vcpus ]
			vm_moves = self.placeVM(vm)
			next_profit = self.cur_profit
			moves += vm_moves
		gold_vms_not_paying = self._get_gold_vms_not_paying()
		self.logger.info("Gold VMs that do not pay AFTER the rebalance_global(): %d", len(gold_vms_not_paying))
		return moves

	def report(self):
		# write the estimated money
		fp = open(self.report_file.name, "a")
		open_sockets = sum([int(bool(len([x for x in s.leaves if isinstance(x, Vcpu)]))) \
						for s in self.tree.children])
		line = str(datetime.now()) + "\t" + str(self.cur_profit) + "\t" + str(open_sockets) + "\n"
		fp.write(line)
		fp.close()

	def toImage(self):
		DotExporter(self.tree).to_picture(self.name + '.png')

if __name__ == '__main__':
	G = 1; S = 0; N = 1; Q = 0; Se = 1; I = 0
	s = ActiManagerSystem([2,1,10], 'a1')
	## (vcpus, is_gold, is_noisy, is_sensitive)
#	vms = [ (1, 1, 1, 1), (2, 0, 0, 0), (1, 0, 0, 0), (2, 0, 1, 1), (1, 0, 0, 0), (2, 0, 1, 1) ]
	vms = [ (1,S,N,I), (2,S,Q,I), (1,S,Q,I), (4,G,N,Se), (2,S,Q,I), (2,S,Q,I), (2,S,Q,I), (2,S,Q,S)]
	for i, v in enumerate(vms):
		s.placeVM(Vm(str(i), v[0], 1, v[1], v[2], v[3], 0))
		print s
