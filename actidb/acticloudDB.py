import pymysql.cursors, time, cPickle, logging, sys

sys.path.append('/home/jim/jimsiak/common/') ## FIXME this should be removed
from config import *

class ActiCloudDBClient():
	def __init__(self, hostname = ACTICLOUDDB_HOSTNAME,
	                   user     = ACTICLOUDDB_USERNAME,
	                   passwd   = ACTICLOUDDB_PASSWORD,
	                   dbname   = ACTICLOUDDB_DBNAME):
		## Setup the logging facility
		logging.basicConfig(stream=sys.stdout, level=logging.INFO,
		                    format='%(asctime)s - %(name)20s - %(message)s',
		                    datefmt='%Y-%m-%d.%H:%M:%S')
		logging.Formatter.converter = time.gmtime
		self.logger = logging.getLogger(self.__class__.__name__)

		## Initialize the mysql connection
		self.connection = pymysql.connect(host=hostname, user=user,
		                                  password=passwd, db=dbname,
		                                  charset='utf8mb4',
		                                  cursorclass=pymysql.cursors.DictCursor)

	def __del__(self):
		self.connection.close()

	def _reconnect_if_lost(self):
		## NOTE(jimsiak): it is inefficient to ping on each and every query but I've
		## tried using the self.connection.open property but it didn't work
		self.connection.ping(reconnect=True)

	def clear_data_from_table(self, tbl_name):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			try:
				sql = "DELETE FROM %s" % tbl_name
				cursor.execute(sql)
				self.connection.commit()
				return 1
			except pymysql.err.ProgrammingError:
				return 0

	def get_db_table_names(self):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SHOW TABLES"
			cursor.execute(sql)
			self.connection.commit()
			result = cursor.fetchall()
			ret = []
			for t in result:
				ret.append(str(t.values()[0]))
			return ret

	def get_vm(self, vm_uuid):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT * FROM `vms` WHERE id=%s"
			cursor.execute(sql, (vm_uuid,))
			self.connection.commit()
			result = cursor.fetchone()
			return result
	def get_vms_by_hostname(self, hostname):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT * FROM vms WHERE hostname=%s"
			cursor.execute(sql, (hostname))
			self.connection.commit()
			result = cursor.fetchall()
			return result
	def insert_host(self, host):
		'''
		@param host: tupple (name, nvcpus, RAM (GB), is_lab)
		'''
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `hosts`
			       (`name`, `nr_pcpus`, `ram_gb`, `is_lab`)
			        VALUES (%s, %s, %s, %s)"""
			cursor.execute(sql, (host[0], host[1], host[2], host[3]))
			self.connection.commit()

	def insert_vm(self, vm_uuid, hostname, nr_vcpus, is_gold, is_noisy,
	              is_sensitive, cost_function):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `vms` 
			       (`id`, `hostname`, `nr_vcpus`, `no_migrations`, `no_moves`,
			        `is_gold`, `is_noisy`, `is_sensitive`, `cost_function`) 
			        VALUES (%s, %s, %s, 0, 0, %s, %s, %s, %s)"""
			cursor.execute(sql, (vm_uuid, hostname, nr_vcpus,
			               is_gold, is_noisy, is_sensitive, cost_function))
			self.connection.commit()
	def remove_vm(self, vm_uuid):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "DELETE FROM `vms` WHERE id=%s"
			cursor.execute(sql, (vm_uuid))
			self.connection.commit()

	def set_vm_attribute(self, uuid, attr, new_val):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = 'UPDATE vms SET %s="%s" WHERE id="%s"' % (attr, str(new_val), uuid)
			cursor.execute(sql)
			self.connection.commit()
			result = cursor.fetchone()
	def inc_vm_attribute(self, uuid, attr):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = 'UPDATE vms SET %s=%s+1 WHERE id="%s"' % (attr, attr, uuid)
			print "SQL:", sql
			cursor.execute(sql)
			self.connection.commit()
			result = cursor.fetchone()

	def resize_vm(self, vm_uuid, flavor_id):
		# FIXME: add flavor to table, or correctly update nr_cpus from flavor
		self.set_vm_attribute(vm_uuid, "nr_cpus", 2)

	def get_nr_gold_vms_by_hostname(self, hostname):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT SUM(is_gold) FROM vms WHERE hostname=%s"
			cursor.execute(sql, (hostname))
			self.connection.commit()
			result = cursor.fetchone()
			ret = result["SUM(is_gold)"]
			return 0 if ret == None else ret
	def get_nr_noisy_vms_by_hostname(self, hostname):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT SUM(is_noisy) FROM vms WHERE hostname=%s"
			cursor.execute(sql, (hostname))
			self.connection.commit()
			result = cursor.fetchone()
			ret = result["SUM(is_noisy)"]
			return 0 if ret == None else ret
	def get_nr_sensitive_vms_by_hostname(self, hostname):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT SUM(is_sensitive) FROM vms WHERE hostname=%s"
			cursor.execute(sql, (hostname))
			self.connection.commit()
			result = cursor.fetchone()
			ret = result["SUM(is_sensitive)"]
			return 0 if ret == None else ret
	def get_nr_gold_vcpus_by_hostname(self, hostname):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT SUM(nr_vcpus) FROM vms WHERE hostname=%s AND is_gold=1"
			cursor.execute(sql, (hostname))
			self.connection.commit()
			result = cursor.fetchone()
			ret = result["SUM(nr_vcpus)"]
			return 0 if ret == None else ret
	def get_nr_silver_vcpus_by_hostname(self, hostname):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT SUM(nr_vcpus) FROM vms WHERE hostname=%s AND is_gold=0"
			cursor.execute(sql, (hostname))
			self.connection.commit()
			result = cursor.fetchone()
			ret = result["SUM(nr_vcpus)"]
			return 0 if ret == None else ret


	def get_vm_attribute(self, uuid, attr, poll_until_found = 1):
		self._reconnect_if_lost()
		retries = 10
		while retries > 0:
			with self.connection.cursor() as cursor:
				sql = "SELECT " + attr + " FROM vms WHERE id=%s"
				cursor.execute(sql, (uuid))
				self.connection.commit()
				result = cursor.fetchone()
				if result != None or poll_until_found == 0:
					break
				retries -= 1
				time.sleep(5)
		return 0 if result == None else result[attr]
	def is_gold_vm(self, uuid, poll_until_found = 0):
		self._reconnect_if_lost()
		retries = 10
		while retries > 0:
			with self.connection.cursor() as cursor:
				sql = "SELECT is_gold FROM vms WHERE id=%s"
				cursor.execute(sql, (uuid))
				self.connection.commit()
				result = cursor.fetchone()
				if result != None or poll_until_found == 0:
					break
				retries -= 1
				time.sleep(5)
		return 0 if result == None else result["is_gold"]
	def is_noisy_vm(self, uuid, poll_until_found = 0):
		self._reconnect_if_lost()
		retries = 10
		while retries > 0:
			with self.connection.cursor() as cursor:
				sql = "SELECT is_noisy FROM vms WHERE id=%s"
				cursor.execute(sql, (uuid))
				self.connection.commit()
				result = cursor.fetchone()
				if result != None or poll_until_found == 0:
					break
				retries -= 1
				time.sleep(5)
		return 0 if result == None else result["is_noisy"]
	def is_sensitive_vm(self, uuid, poll_until_found = 1):
		self._reconnect_if_lost()
		retries = 10
		while retries > 0:
			with self.connection.cursor() as cursor:
				sql = "SELECT is_sensitive FROM vms WHERE id=%s"
				cursor.execute(sql, (uuid))
				self.connection.commit()
				result = cursor.fetchone()
				if result != None or poll_until_found == 0:
					break
				retries -= 1
				time.sleep(5)
		return 0 if result == None else result["is_sensitive"]
	def get_nr_vcpus(self, uuid):
		self._reconnect_if_lost()
		return self.get_vm_attribute(uuid, "nr_vcpus", 1)

	def get_moves(self, uuid):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT no_moves FROM vms WHERE id=%s"
			cursor.execute(sql, (uuid))
			self.connection.commit()
			result = cursor.fetchone()
			ret = result["no_moves"]
			return 0 if ret == None else ret
	def set_moves(self, uuid, new_moves):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "UPDATE vms SET no_moves=%s WHERE id=%s"
			cursor.execute(sql, (new_moves,uuid))
			self.connection.commit()
	def cost_function(self, uuid):
		self._reconnect_if_lost()
		return self.get_vm_attribute(uuid, "cost_function", 1)

	def insert_model(self, bench_name, nr_vcpus, model):
		self._reconnect_if_lost()
		p_model = cPickle.dumps(model)
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `healthy_state_models` 
			       (`bench_name`, `nr_vcpus`, `model`) 
			        VALUES (%s, %s, %s)"""
			cursor.execute(sql, (bench_name, nr_vcpus, p_model))
			self.connection.commit()
	def get_model(self, bench_name, nr_vcpus):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = "SELECT model FROM healthy_state_models WHERE bench_name=%s AND nr_vcpus=%s"
			cursor.execute(sql, (bench_name, nr_vcpus))
			self.connection.commit()
			result = cursor.fetchone()
			ret = cPickle.loads(result["model"])
			return ret ## May be None
	def insert_bench_isolation_performance(self, bench_name, nr_vcpus, performance, unit):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `bench_isolation_performance`
			       (`bench_name`, `nr_vcpus`, `performance`, `unit`)
			        VALUES (%s, %s, %s, %s)"""
			cursor.execute(sql, (bench_name, nr_vcpus, performance, unit))
			self.connection.commit()
	def get_bench_isolation_performance(self, bench_name, nr_vcpus):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """SELECT performance, unit FROM bench_isolation_performance
			         WHERE bench_name=%s AND nr_vcpus=%s"""
			cursor.execute(sql, (bench_name, nr_vcpus))
			self.connection.commit()
			result = cursor.fetchone()
			ret = (result["performance"], result["unit"])
			return (0.0, "throughput") if ret == None else ret

	def insert_bench_isolation_perf_metric(self, bench_name, nr_vcpus, time, metric, value):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `bench_isolation_perf_metrics`
			       (`bench_name`, `nr_vcpus`, `time`, `metric`, `value`)
			        VALUES (%s, %s, %s, %s, %s)"""
			cursor.execute(sql, (bench_name, nr_vcpus, time, metric, value))
			self.connection.commit()


	def insert_heartbeat(self, vm_uuid, time, performance, bench_name, nr_vcpus):
		self._reconnect_if_lost()
		vm_db = self.get_vm(vm_uuid)
		hostname = str(vm_db['hostname'])
		(isolation_performance, unit) = self.get_bench_isolation_performance(bench_name, nr_vcpus)
		if (unit == "time"):
			slowdown = performance / isolation_performance
		else:
			slowdown = isolation_performance / performance
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `vm_heartbeats` 
			        VALUES (%s, %s, %s, %s, %s, %s)"""
			cursor.execute(sql, (vm_uuid, time, performance, isolation_performance,
			                     slowdown, hostname))
			self.connection.commit()

	def insert_external_profit_report(self, hostname, time, new_vm_uuid,
	                                  profit_before, profit_after, profit_diff):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `external_profit_reports`
			        VALUES (%s, %s, %s, %s, %s, %s)"""
			cursor.execute(sql, (hostname, time, new_vm_uuid, profit_before,
			                     profit_after, profit_diff))
			self.connection.commit()
	def insert_internal_profit_report(self, hostname, time, profit):
		self._reconnect_if_lost()
		with self.connection.cursor() as cursor:
			sql = """INSERT INTO `internal_profit_reports`
			        VALUES (%s, %s, %s)"""
			cursor.execute(sql, (hostname, time, profit))
			self.connection.commit()
