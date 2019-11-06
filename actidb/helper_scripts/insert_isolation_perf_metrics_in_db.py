import os, sys, json, datetime
sys.path.append('../')
from acticloudDB import ActiCloudDBClient

if (len(sys.argv) < 2):
	print "usage: %s <perf_output_files ...>" % sys.argv[0]
	sys.exit(1)

actiDB = ActiCloudDBClient()

perf_metrics = ['branches', 'branch-misses', 'cycles', 'instructions', 'context-switches',
                'cpu-migrations', 'page-faults', 'LLC-loads', 'LLC-load-misses',
                'dTLB-loads', 'dTLB-load-misses', 'mem-loads', 'mem-stores' ]

starting_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=30)

total_files = len(sys.argv[1:])

for i, filename in enumerate(sys.argv[1:]):

	print "File %d of %d" % (i+1, total_files)

	tokens = os.path.basename(filename).split('-')
	bench_name = tokens[1]
	nr_vcpus = int(tokens[2].replace("vcpus.perf", ""))
	time = starting_time

	fp = open(filename)
	line = fp.readline()
	while line:
		tokens = line.split()
		if (tokens[2] in perf_metrics or tokens[3] in perf_metrics):
			metric = tokens[2] if tokens[2] in perf_metrics else tokens[3]
			value = 0.0 if tokens[1] == "<not" else float(tokens[1])
			time_str = time.strftime("%Y-%m-%d.%X")
			if (metric == perf_metrics[-1]):
				time += datetime.timedelta(seconds=1)

			actiDB.insert_bench_isolation_perf_metric(bench_name, nr_vcpus, time_str, metric, value)
		line = fp.readline()

fp.close()
