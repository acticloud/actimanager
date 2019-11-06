import os, sys, json
sys.path.append('../')
sys.path.append('../../workload/')
from acticloudDB import ActiCloudDBClient
import benchmarks

if (len(sys.argv) != 2):
	print "usage: %s <executor_output_file>" % sys.argv[0]
	sys.exit(1)

actiDB = ActiCloudDBClient()

filename = sys.argv[1]
fp = open(filename)

already_in = dict()
line = fp.readline()
while line:
	line = fp.readline()
	if "EVENT" in line and "heartbeat" in line:
		tokens = line.split(' - ')
		event_output = tokens[2].replace("EVENT: ", "")
		json_data = json.loads(event_output)
		nr_vcpus = json_data['vcpus']
		bench_name = json_data['bench']
		if bench_name == "stress-cpu":
			bench_name += "-" + str(json_data['load'])
		bench_name = bench_name.replace("-to-completion", "")

		if (bench_name, nr_vcpus) in already_in:
			continue
		already_in[(bench_name, nr_vcpus)] = 1
		output = json_data['output']
		(performance, unit) = benchmarks.bench_get_perf_from_output(bench_name, nr_vcpus,
		                                                            output)
		actiDB.insert_bench_isolation_performance(bench_name, nr_vcpus, performance, unit)

fp.close()
