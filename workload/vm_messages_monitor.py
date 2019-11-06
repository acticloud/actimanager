import socket, json, threading, sys, time, logging, traceback
import benchmarks

sys.path.append('../actidb/')
from acticloudDB import ActiCloudDBClient

HOST_DEFAULT = ""
PORT_DEFAULT = 8080

class VmMessagesMonitor():
	def __init__(self, host=HOST_DEFAULT, port=PORT_DEFAULT):
		self.host = host
		self.port = port
		self.monitor_thread_done = 0

		self._setup_logger()
		self.actidb_client = ActiCloudDBClient()

	def _setup_logger(self):
		self.logger = logging.getLogger(__name__)

	def _monitor_thread_function(self, s):
		while not self.monitor_thread_done:
			try:
				conn, addr = s.accept()
				conn.settimeout(10)
				data = ""
				try:
					while 1:
						new_data = conn.recv(1024)
						if not new_data:
							break
						data += new_data
					self.logger.info("EVENT: %s", data.strip())

					json_data = json.loads(data)
					if "event" in json_data:
						event = json_data["event"]
						if event == "heartbeat":
							bench_name = json_data["bench"].replace("-to-completion", "")
							nr_vcpus = json_data["vcpus"]
							vm_uuid = json_data["vm_uuid"]
							time = json_data["time"]
							output = json_data["output"]
							(performance, unit) = benchmarks.bench_get_perf_from_output(bench_name, 1,
							                                                    output)
							self.actidb_client.insert_heartbeat(vm_uuid, time, performance,
							                                    bench_name, nr_vcpus)
						elif event == "acticloud-external-openstack-filter-profit-report":
							hostname = json_data["hostname"]
							time = json_data["time"]
							new_vm_uuid = json_data["new-vm-uuid"]
							profit_before = json_data["profit-before"]
							profit_after  = json_data["profit-after"]
							profit_diff   = json_data["profit-diff"]
							self.actidb_client.insert_external_profit_report(hostname, time,
							        new_vm_uuid, profit_before, profit_after, profit_diff)
						elif event == "internal-profit-report":
							hostname = json_data["hostname"]
							time = json_data["time"]
							profit = json_data["profit-value"]
							self.actidb_client.insert_internal_profit_report(hostname, time,
							                                                 profit)
				except:
					print(traceback.format_exc())
					self.logger.error("Something went wrong when reading data from the socket.")
				conn.close()
			except:
				pass

	def spawn_monitor_thread(self):
		retries = 10
		while retries > 0:
			try:
				self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.socket.bind((self.host, self.port))
				self.socket.listen(1000)
				self.socket.settimeout(5)
				break
			except socket.error:
				self.logger.info("Socket initialization error. Retrying")
				time.sleep(10)
				retries -= 1

		if retries == 0:
			self.logger.info("Failed to initiliaze socket. Exiting")
			sys.exit(1)
			
		self.monitor_thread = threading.Thread(target=self._monitor_thread_function,
			                                       args=(self.socket,))
		self.monitor_thread.start()

	def stop_monitor_thread(self):
		self.monitor_thread_done = 1
		self.monitor_thread.join()
		self.socket.close()
