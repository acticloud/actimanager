import sys, random, time, math, datetime, signal, calendar, logging
from vm_messages_monitor import *
from benchmarks import *

sys.path.append('../common/')
from openstack_client import OpenstackClient
import event_logger

## Setup the logging facility
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(message)s', datefmt='%Y-%m-%d.%H:%M:%S')
logging.Formatter.converter = time.gmtime
logger = logging.getLogger("executor")

## Inititalize Openstack Client
ost_client = OpenstackClient()

def get_image_by_bench(bench):
	img_name = bench['openstack_image']
	for img in ost_client.get_images():
		if img_name in img.name:
			return img

def spawn_vm(seq_num, vm_chars, wait_until_finished):
	'''
		Spawns a VM and returns 0 if an error has occured
	'''
	vcpus = vm_chars['nr_vcpus']
	is_gold = vm_chars['is_gold']
	is_noisy = vm_chars['is_noisy']
	is_sensitive = vm_chars['is_sensitive']
	bench = vm_chars['bench']
	runtime = vm_chars['runtime']
	run_mode = bench['run_mode']

	gold_str = "gold" if is_gold else "silver"
	flavor_name = "acticloud." + str(vcpus) + "core." + gold_str
	flavor = ost_client.get_flavor_by_name(flavor_name)
	bench_name = bench_get_name(bench)

	times_to_run = 0
	if run_mode == "fixed_time":
		run_mode += "-" + str(runtime)
	elif run_mode == "to_completion":
		runtime_isolation = bench['runtime_isolation']
		times_to_run = (runtime * 60.0) / runtime_isolation
		bench_name += "-%d_times" % times_to_run
	vm_name = "acticloud-" + gold_str + "-" + bench_name + "-" + run_mode
	image = get_image_by_bench(bench)
	udata = get_vm_userdata(seq_num, vcpus, bench, runtime, times_to_run)
	metadata = {'seq_num': str(seq_num), 'is_gold': str(is_gold),
	            'is_noisy': str(is_noisy), 'is_sensitive': str(is_sensitive)}

	start_time = time.time()
	new_vm = ost_client.nova.servers.create(vm_name, image, flavor, userdata=udata,
	                             key_name="rootkey", meta=metadata) 
#	                             key_name="rootkey", meta=metadata,
#	                             availability_zone="nova:acticloud1")

	## Wait for the VM to leave the status "BUILD"
	while True:
		new_vm_uuid = new_vm.id
		new_vm = ost_client.get_vm(new_vm_uuid)
		while new_vm.status == "BUILD":
			new_vm = ost_client.get_vm(new_vm_uuid)
			## Sleep for a small duration, to avoid too many openstack requests
			time.sleep(5)
		break
	if new_vm.status == "ERROR":
		logger.info("VM %s failed to spawn with status %s", vm_name, new_vm.status)
		return 0
	end_time = time.time()

	event_logger.log_event({'vm_seq_num': seq_num, 'event': 'spawn',
	                        'host': getattr(new_vm, 'OS-EXT-SRV-ATTR:host'),
	                        'vcpus': vcpus})
#	logger.info('EVENT: {"vm_seq_num": %d, "event": "spawn" , "time": "%s", "host": "%s", "vcpus": %d}',
#	            seq_num, time_now,
#	            getattr(new_vm, 'OS-EXT-SRV-ATTR:host'), vcpus)
	time_now = datetime.datetime.utcnow().strftime("%Y-%m-%d.%X")
	logger.info("Spawned new VM with seq_num: %d and name: %s at: %s (in %4.2f seconds) on host %s",
	         seq_num, vm_name, time_now, end_time - start_time,
			 getattr(new_vm, 'OS-EXT-SRV-ATTR:host'))

	## If necessary wait for the VM to finish its execution
	if wait_until_finished:
		logger.info("Waiting for VM %d to finish its execution", seq_num)
		new_vm = ost_client.get_vm(new_vm_uuid)
		while not new_vm.status in ["SHUTOFF", "ERROR"]:
			time.sleep(1*60)
			new_vm = ost_client.get_vm(new_vm_uuid)
		if new_vm.status == "ERROR":
			return 0

	return 1

def count_and_delete_finished_vms():
	logger.info("Deleting VMs with status of ERROR and SHUTOFF...")
	err = 0
	shutoff = 0
	for vm in ost_client.get_vms():
		if not vm.name.startswith("acticloud-"):
			continue
		if vm.status == "ERROR":
			err += 1
			ost_client.nova.servers.delete(vm)
		elif vm.status == "SHUTOFF":
			shutoff += 1
			ost_client.nova.servers.delete(vm)
	if err + shutoff > 0:
		logger.info("Sleeping for 10 seconds to allow the %d VMs to be deleted.",
		             err + shutoff)
		time.sleep(10)
	return [err, shutoff]

VCPUS_PROPS = [ [50, 25, 15, 10],
                [1,  2,  4, 8] ]
ISGOLD_PROPS = [ [80, 20],
                 [0,   1] ]
ISNOISY_PROPS = [ [50, 50],
                  [0,  1] ]
RUNTIMES = [15, 20, 25, 30, 35, 40, 45]  ## minutes

spawned_vms = { 'total': 0, 'gold': 0, 'noisy': 0, 'sensitive': 0 }
spawned_vms_nr_vcpus = { 1: 0, 2: 0, 4: 0, 8: 0 }

def get_random_with_props(arr):
	prop = random.random() * 100
	ind = -1
	current_prop = 0
	while prop >= current_prop:
		ind += 1
		current_prop += arr[0][ind]
	return arr[1][ind]

def get_new_vm_characteristics():
	vm_chars = dict()
	vm_chars['nr_vcpus'] = get_random_with_props(VCPUS_PROPS)
	vm_chars['is_gold'] = get_random_with_props(ISGOLD_PROPS)
	vm_chars['is_noisy'] = get_random_with_props(ISNOISY_PROPS)
	vm_chars['bench'] = random.choice(benches_per_category[vm_chars['is_noisy']])
	vm_chars['is_sensitive'] = vm_chars['bench']['is_sensitive']
	vm_chars['runtime'] = random.choice(RUNTIMES)
	return vm_chars

def spawn_vm_with_props(seq_num, vm_chars, wait_until_finished=0):
	'''
		Spawns a VM and returns 0 if an error has occured
	'''
	ret = spawn_vm(seq_num, vm_chars, wait_until_finished)
	if ret != 0:
		spawned_vms['total'] += 1
		spawned_vms['gold'] += vm_chars['is_gold']
		spawned_vms['noisy'] += vm_chars['is_noisy']
		spawned_vms['sensitive'] += vm_chars['is_sensitive']
		spawned_vms_nr_vcpus[vm_chars['nr_vcpus']] += 1
	return ret

def wait_for_vms_to_finish(timeout_minutes):
	'''
	Waits until all the VMs with prefix="acticloud-" finish their execution.
	If 'timeout_minutes' minutes have passed, it kills all the remaining VMs.
	'''
	logger.info("Waiting for the remaining VMs to finish their execution")
	successful_vms = 0
	unsuccessful_vms = 0
	stucked_vms = 0
	wait_vms_start_time = time.time()
	while 1:
		## If more than 'timeout_minutes' minutes have passed, some VMs are stuck
		## I have added timeouts in userdata codes, but also leave this here
		## as an additional measure to avoid getting stuck
		if (time.time() - wait_vms_start_time > timeout_minutes * 60.0):
			logger.info("More than %d minutes have passed. Some VMs are stuck, deleting them.", timeout_minutes)
			stucked_vms = ost_client.delete_existing_vms(prefix="acticloud-")
			logger.info("Manually deleted %d VMs", stucked_vms)
			break

		## Clear the VMs in state SHUTOFF and ERROR
		[err, shutoff] = count_and_delete_finished_vms()
		successful_vms += shutoff
		unsuccessful_vms += err
		[dc_tot_vcpus, dc_used_vcpus] = ost_client.get_data_center_vcpus()
		if (dc_used_vcpus == 0):
			break
		time.sleep(POLLING_PERIOD * 60)

	wait_vms_end_time = time.time()
	wait_vms_tot_time = wait_vms_end_time - wait_vms_start_time
	logger.info("All VMs have finished their execution after %4.2lf minutes",
	            wait_vms_tot_time / 60.0)

	return [successful_vms, unsuccessful_vms, stucked_vms]


POLLING_PERIOD = 5 # Wake up every 5 minutes to check utilization
BENCHMARK_TIME = 120 # Duration of complete benchmark in minutes
def benchmark(desired_utilization = 50):
	logger.info("======================================================================>")
	logger.info("===> Benchmark Start")
	logger.info("===>   Desired DC Utilization: %d%%", desired_utilization)
	logger.info("===>   Gold VMs ratio: %d%%", ISGOLD_PROPS[0][1])
	logger.info("===>   Noisy VMs ratio: %d%%", ISNOISY_PROPS[0][1])
	logger.info("===>   VCPU propabilities: 1 vcpu: %d%% 2 vcpus: %d%% 4 vcpus: %d%% 8 vcpus: %d%%",
	            VCPUS_PROPS[0][0], VCPUS_PROPS[0][1], VCPUS_PROPS[0][2], VCPUS_PROPS[0][3])
	logger.info("===>   Execution Time: %d minutes", BENCHMARK_TIME)
	logger.info("===>   Utilization Checked every: %d minutes", POLLING_PERIOD)

	## RNG initialization
	random.seed(13)

	vms_spawned = 0
	successful_vms = 0
	unsuccessful_vms = 0
	previous_vm_was_error = 0

	bench_start_time = time.time()
	times_to_poll = BENCHMARK_TIME / POLLING_PERIOD
	while times_to_poll > 0:
		## Reduce the VM runtimes on the last periodic checks
		global RUNTIMES
		if vms_spawned < 50:
			RUNTIMES = [35, 40, 45]
		elif vms_spawned == 50:
			RUNTIMES = [15, 20, 25, 30, 35, 40, 45]  ## minutes

		logger.info("---------------------------------------------------------------------->")
		logger.info("---> Periodic checking of utilization (%d remaining)", times_to_poll-1)

		## Clear the VMs in state SHUTOFF and ERROR
		[err, shutoff] = count_and_delete_finished_vms()
		successful_vms += shutoff
		unsuccessful_vms += err

		## Checking utilization of the data center
		[dc_tot_vcpus, dc_used_vcpus] = ost_client.get_data_center_vcpus()
		vcpus_goal = int(math.ceil((desired_utilization / 100.0) * dc_tot_vcpus))
		vcpus_to_spawn = vcpus_goal - dc_used_vcpus
		logger.info("Data center utilization %4.2f%% ( %d / %d vcpus used )",
		             float(dc_used_vcpus) / float(dc_tot_vcpus) * 100.0, dc_used_vcpus, dc_tot_vcpus)

		## Spawn VMs to reach the desired utilization level
		vms_spawn_tot_time = 0
		if vcpus_to_spawn > 0:
			logger.info("Going to spawn %d vcpus to reach total %d vcpus (%d%% utilization)" %
			         (vcpus_to_spawn, vcpus_goal, desired_utilization))
			vms_spawned_saved = vms_spawned
			vms_spawn_start_time = time.time()
			while (vcpus_to_spawn > 0):
				if not previous_vm_was_error:
					new_vm_chars = get_new_vm_characteristics()
				new_vm_vcpus = new_vm_chars['nr_vcpus']
				if spawn_vm_with_props(vms_spawned, new_vm_chars) == 0:
					logger.info("Failed to spawn VM %d", vms_spawned)
					previous_vm_was_error = 1
					break
				previous_vm_was_error = 0
				vcpus_to_spawn -= new_vm_vcpus
				vms_spawned += 1
			vms_spawn_end_time = time.time()
			vms_spawn_tot_time = vms_spawn_end_time - vms_spawn_start_time
			logger.info("Spawned %d VMs in %4.2lf seconds",
			            vms_spawned - vms_spawned_saved, vms_spawn_tot_time)
		else:
			logger.info("Desired utilization is reached: %d%% (%d vcpus / %d total)" %
			          (desired_utilization, dc_used_vcpus, dc_tot_vcpus))

		if (vms_spawn_tot_time < POLLING_PERIOD * 60):
			logger.info("Sleeping for %d seconds", POLLING_PERIOD * 60 - vms_spawn_tot_time)
			time.sleep(POLLING_PERIOD * 60 - vms_spawn_tot_time)
		else:
			logger.info("Not sleeping since POLLING_PERIOD has already passed")
		times_to_poll -= 1
		logger.info("---------------------------------------------------------------------->")

	## Wait for the remaining VMs to finish their execution
	ret = wait_for_vms_to_finish(60)
	successful_vms += ret[0]
	unsuccessful_vms += ret[1]
	stucked_vms = ret[2]

	bench_end_time = time.time()
	bench_exec_time = bench_end_time - bench_start_time

	logger.info("===> Benchmark End")
	logger.info("===>   Actual Execution time: %4.2lf minutes", bench_exec_time / 60.0)
	logger.info("===>   Total VMs spawned: %d", vms_spawned)
	logger.info("===>   Successfull VMs spawned: %d", successful_vms)
	logger.info("===>   Unsuccessfull VMs spawned: %d", unsuccessful_vms)
	logger.info("===>   VMs that were manually delete (they were probably stuck): %d", stucked_vms)
	logger.info("===>   Total VMs: %d Gold VMs: %d (%.2lf%%) Noisy VMs: %d (%.2lf%%) Sensitive VMs: %d (%.2lf%%)",
	            spawned_vms['total'], spawned_vms['gold'], 
				float(spawned_vms['gold']) / max(1, spawned_vms['total']) * 100.0,
				spawned_vms['noisy'],
				float(spawned_vms['noisy']) / max(1, spawned_vms['total']) * 100.0,
	            spawned_vms['sensitive'],
				float(spawned_vms['sensitive']) / max(1, spawned_vms['total']) * 100.0)
	logger.info("======================================================================>")

def generate_vms_queue(nvms = 200, nvcpus_start = 40, rate = 2.0):
	'''
	'nvms': number of vms to generate in total
	'nvcpus_start': number of vcpus to populate the data center in the beginning
	'rate': rate (in minutes) in which new VMs are added in the queue
	'''
	## RNG initialization
	random.seed(13)

	vms = []

	## The first batch, to reach the desired starting utilization
	nvcpus = nvcpus_start
	while nvcpus > 0:
		new_vm = get_new_vm_characteristics()
		vms.append([0.0, new_vm])
		nvcpus -= new_vm['nr_vcpus']
		nvms -= 1

	cur_minute = 30.0
	while nvms > 0:
		nvcpus = 8 ## How many vcpus to spawn in this minute
		while nvcpus > 0:
			new_vm = get_new_vm_characteristics()
			vms.append([cur_minute, new_vm])
			nvcpus -= new_vm['nr_vcpus']
			nvms -= 1
		cur_minute += rate

	return vms

def print_vms_queue(vms):
	vms_ratio = {'total': 0, 'gold': 0, 'noisy': 0, 'sensitive': 0,
	             'vcpus': { 1: 0, 2: 0, 4: 0, 8:0 }}
	different_benchnames = []
	logger.info("++++++++++++++++++++++++++")
	logger.info("+++ VMs queue information:")

	logger.info("+++ Start of VMs queue +++")
	for i, [vm_time, vm_chars] in enumerate(vms):
		logger.info("%3d %4.1f %2d %2s %2s %2s %10s", i, vm_time,
		            vm_chars['nr_vcpus'],
		            "G" if vm_chars['is_gold'] == 1 else "S",
		            "N" if vm_chars['is_noisy'] == 1 else "Q",
		            "S" if vm_chars['is_sensitive'] == 1 else "I",
		            vm_chars['bench']['name'])
		vms_ratio['total'] += 1
		vms_ratio['gold'] += vm_chars['is_gold']
		vms_ratio['noisy'] += vm_chars['is_noisy']
		vms_ratio['sensitive'] += vm_chars['is_sensitive']
		vms_ratio['vcpus'][vm_chars['nr_vcpus']] += 1
		if not vm_chars['bench']['name'] in different_benchnames:
			different_benchnames.append(vm_chars['bench']['name'])
	logger.info("+++ End of VMs queue +++")

	logger.info("+++   Total VMs: %d", vms_ratio['total'])
	logger.info("+++   Total VCPUs: %d", sum(vms_ratio['vcpus'].values()))
	logger.info("+++   Gold VMs: %d ( %5.2f %% )", vms_ratio['gold'],
	                                   float(vms_ratio['gold'])/vms_ratio['total']*100.0)
	logger.info("+++   Noisy VMs: %d ( %5.2f %% )", vms_ratio['noisy'],
	                                   float(vms_ratio['noisy'])/vms_ratio['total']*100.0)
	logger.info("+++   Sensitive VMs: %d ( %5.2f %% )", vms_ratio['sensitive'],
	                                   float(vms_ratio['sensitive'])/vms_ratio['total']*100.0)
	logger.info("+++   Different benchmarks: %d", len(different_benchnames))
	logger.info("++++++++++++++++++++++++++")

def benchmark_from_queue(nvcpus_start, rate):
	'''
	This benchmark generates an array of [minute, vm_characteristics] which
	represent the minute after which each VM is spawned and its characteristics and uses this
	queue of VMs throughout its execution.
	'''
	SLEEP_INTERVAL_SECONDS = 60.0 ## Seconds to sleep before checking for available VMs in the queue
	BENCH_DURATION_MINUTES = 2 * 60.0 ## How much time will the benchmark last?

	logger.info("======================================================================>")
	logger.info("===> Benchmark that uses a queue of VMs starts.")
	logger.info("===>   Execution Time: %d minutes", BENCH_DURATION_MINUTES)

	## Generate the queue of VMs to be executed
	vms = generate_vms_queue(nvcpus_start = nvcpus_start, rate = rate)
	print_vms_queue(vms)

	start_epoch = calendar.timegm(time.gmtime())

	successful_vms = 0
	unsuccessful_vms = 0
	vms_spawned = 0
	minutes_elapsed = 0

	bench_start_time = time.time()
	while len(vms) > 0 and minutes_elapsed <= BENCH_DURATION_MINUTES:
		minutes_elapsed = (calendar.timegm(time.gmtime()) - start_epoch) / 60.0

		logger.info("---------------------------------------------------------------------->")
		logger.info("Starting benchmark loop, current time: %4.2f minutes.", minutes_elapsed)

		## Clear the VMs in state SHUTOFF and ERROR
		[err, shutoff] = count_and_delete_finished_vms()
		successful_vms += shutoff
		unsuccessful_vms += err

		## Get all the available VMs, i.e., VMs with 'time' less than the current time
		available_vms = [ x for x in vms if x[0] <= minutes_elapsed ]
		logger.info("Number of available VMs for this benchmark loop: %d", len(available_vms))

		## Check for available VMs and spawn them
		spawned_vms_arrival_times = dict() ## keys are arrival times and values are count of VMs
		vms_spawned_saved = vms_spawned
		vms_spawn_start_time = time.time()
		for [vm_time, vm_chars] in available_vms:
			if spawn_vm_with_props(vms_spawned, vm_chars) == 0:
				logger.info("Failed to spawn VM %d", vms_spawned)
				previous_vm_was_error = 1
				break
			if (not vm_time in spawned_vms_arrival_times):
				spawned_vms_arrival_times[vm_time] = 0
			spawned_vms_arrival_times[vm_time] += 1
			vms_spawned += 1
			vms.remove([vm_time, vm_chars])
		vms_spawn_end_time = time.time()
		vms_spawn_tot_time = vms_spawn_end_time - vms_spawn_start_time
		logger.info("Spawned %d VMs in %4.2lf seconds",
		            vms_spawned - vms_spawned_saved, vms_spawn_tot_time)
		arrival_times_str = ""
		for k in sorted(spawned_vms_arrival_times.keys()):
			arrival_times_str += (" %f: %d" % (k, spawned_vms_arrival_times[k]))
		logger.info("Spawned VMs arrival times: %s", arrival_times_str)

		logger.info("Sleeping for %d seconds", SLEEP_INTERVAL_SECONDS)
		time.sleep(SLEEP_INTERVAL_SECONDS)
		logger.info("---------------------------------------------------------------------->")

	## Wait for the remaining VMs to finish their execution
	ret = wait_for_vms_to_finish(60)
	successful_vms += ret[0]
	unsuccessful_vms += ret[1]
	stucked_vms = ret[2]

	bench_end_time = time.time()
	bench_exec_time = bench_end_time - bench_start_time

	logger.info("===> Benchmark End")
	logger.info("===>   Actual Execution time: %4.2lf minutes", bench_exec_time / 60.0)
	logger.info("===>   Total VMs spawned: %d", vms_spawned)
	logger.info("===>   Successfull VMs spawned: %d", successful_vms)
	logger.info("===>   Unsuccessfull VMs spawned: %d", unsuccessful_vms)
	logger.info("===>   VMs that were manually delete (they were probably stuck): %d", stucked_vms)
	logger.info("===>   Total VMs: %d Gold VMs: %d (%.2lf%%) Noisy VMs: %d (%.2lf%%) Sensitive VMs: %d (%.2lf%%)",
	            spawned_vms['total'], spawned_vms['gold'], 
				float(spawned_vms['gold']) / max(1, spawned_vms['total']) * 100.0,
				spawned_vms['noisy'],
				float(spawned_vms['noisy']) / max(1, spawned_vms['total']) * 100.0,
	            spawned_vms['sensitive'],
				float(spawned_vms['sensitive']) / max(1, spawned_vms['total']) * 100.0)
	logger.info("======================================================================>")

def benchmark_isolation():
	logger.info("======================================================================>")
	logger.info("===> Benchmark Isolation Start")
	logger.info("===> Going to run each VM from the benchmarks file in isolation.")

	vms_spawned = 0
	successful_vms = 0
	unsuccessful_vms = 0

	bench_start_time = time.time()

	for bench in benches:
		for nr_vcpus in VCPUS_PROPS[1]:
			## Clear the previous VMs in state SHUTOFF and ERROR
			[err, shutoff] = count_and_delete_finished_vms()
			successful_vms += shutoff
			unsuccessful_vms += err
			new_vm_chars = dict()
			new_vm_chars['nr_vcpus'] = nr_vcpus
			new_vm_chars['is_gold'] = 1
			new_vm_chars['is_noisy'] = bench['is_noisy']
			new_vm_chars['is_sensitive'] = bench['is_sensitive']
			new_vm_chars['bench'] = bench
			## 5 Minutes if fixed-time, else one execution
			new_vm_chars['runtime'] = 5 if   bench['run_mode'] == "fixed_time" \
			                            else math.ceil(bench['runtime_isolation'] / 60.0)
			if spawn_vm_with_props(vms_spawned, new_vm_chars, 1) == 0:
				logger.info("Failed to spawn VM %d", vms_spawned)
				break
			vms_spawned += 1
	
	## Clear the last spawned VM
	[err, shutoff] = count_and_delete_finished_vms()
	successful_vms += shutoff
	unsuccessful_vms += err

	bench_end_time = time.time()
	bench_exec_time = bench_end_time - bench_start_time

	logger.info("===> Benchmark End")
	logger.info("===>   Actual Execution time: %4.2lf minutes", bench_exec_time / 60.0)
	logger.info("===>   Total VMs spawned: %d", vms_spawned)
	logger.info("===>   Successfull VMs spawned: %d", successful_vms)
	logger.info("===>   Unsuccessfull VMs spawned: %d", unsuccessful_vms)
	logger.info("======================================================================>")

vm_messages_monitor = None

def signal_handler(signum, frame):
	logger.info("-> Caught a signal, exiting...")
	vm_messages_monitor.stop_monitor_thread()
	sys.exit(1)

if __name__ == '__main__':
	if len(sys.argv) < 4:
		logger.error("usage: %s <%% gold VMs> <%% noisy VMs> <%% desired DC utilization>", sys.argv[0])
		logger.error("     If utilization is set to -1 each workload VM is run in isolation")
		sys.exit(1)

	## Clean the data center from existing VMs
	ret = ost_client.delete_existing_vms(prefix="acticloud-")
	logger.info("Sleeping for 10 seconds to allow all %d VMs to be deleted.", ret)
	time.sleep(10)

	vm_messages_monitor = VmMessagesMonitor()
	vm_messages_monitor.spawn_monitor_thread()
	signal.signal(signal.SIGTERM, signal_handler)
	signal.signal(signal.SIGINT, signal_handler)

	## Read the command line arguments
	gold_ratio = int(sys.argv[1])
	if gold_ratio > 100:
		logger.error("Gold VMs ratio must be <= 100")
		signal_handler(0, 0)
	ISGOLD_PROPS[0][0] = 100 - gold_ratio
	ISGOLD_PROPS[0][1] = gold_ratio

	noisy_ratio = int(sys.argv[2])
	if noisy_ratio > 100:
		logger.error("noisy VMs ratio must be <= 100")
		signal_handler(0, 0)
	ISNOISY_PROPS[0][0] = 100 - noisy_ratio
	ISNOISY_PROPS[0][1] = noisy_ratio

#	desired_utilization = int(sys.argv[3])
#	if desired_utilization == -1:
#		benchmark_isolation()
#	else:
#		benchmark(desired_utilization)

	benchmark_from_queue(int(sys.argv[4]), float(sys.argv[5]))

	vm_messages_monitor.stop_monitor_thread()
	sys.exit(0)
