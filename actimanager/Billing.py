silver_money = 1.0
gold_money = 10.0
silver_tolerate = 4.5
gold_tolerate = 1.2
server_std_cost = 20.0
socket_cost = 5.0

class Batch(object):
	def __init__(self):
		self.money = silver_money
		self.tolerate = silver_tolerate

	def cost(self, slowdown):
		return self.money / slowdown if slowdown < self.tolerate else 0.0

class UserFacing(object):
	def __init__(self, is_gold = 0):
		self.money = silver_money if not is_gold else gold_money
		self.tolerate = silver_tolerate if not is_gold else gold_tolerate

	def cost(self, slowdown):
		return self.money if slowdown < self.tolerate else 0.0

class ServerCost(object):
	def __init__(self, cores):
		self._cost = server_std_cost

	@property
	def cost(self):
		return self._cost

class SocketCost(object):
	def __init__(self, socket_number, server_cost):
		self._cost = socket_cost

	@property
	def cost(self):
		return self._cost
