import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

perf_events = ["branches", "branch-misses", "cycles", "instructions", "context-switches",
              "cpu-migrations", "page-faults", "LLC-loads", "LLC-load-misses",
              "dTLB-loads", "dTLB-load-misses", "mem-loads", "mem-stores"]

def read_perf_output_to_dict(filename):
	ret = dict()
	f = open(filename)
	line = f.readline()
	while line:
		tokens = line.split()
		if (len(tokens) < 3):
			line = f.readline()
			continue

		perf_event = tokens[2]
		if "counted" in tokens[2]:
			perf_event = tokens[3]

		if (perf_event in perf_events):
			if "counted" in tokens[2]:
				metric = 0.0
			else:
				metric = float(tokens[1])

			if not perf_event in ret:
				ret[perf_event] = []
			ret[perf_event].append(metric)

		line = f.readline()

	return ret

if (len(sys.argv) < 2):
	print "usage: %s <perf_output_files ...>" % sys.argv[0]
	sys.exit(1)

ax = plt.subplot("111")

for filename in sys.argv[1:]:
	results = read_perf_output_to_dict(filename)
	for k in results:
		print k, len(results[k])

	to_plot = results["mem-stores"]
	ax.plot(np.arange(len(to_plot)), to_plot, label=filename)

leg = ax.legend(ncol=1,loc="upper left",prop={'size':12})
plt.savefig("lol.png")
