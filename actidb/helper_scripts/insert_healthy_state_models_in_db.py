import os, sys
sys.path.append('../')
sys.path.append('../../actimanager/')
from acticloudDB import ActiCloudDBClient
import HealthyStateModel

if (len(sys.argv) < 2):
	print "usage: %s <perf_output_files>" % sys.argv[0]
	sys.exit(1)

actiDB = ActiCloudDBClient()

for filename in sys.argv[1:]:
	tokens = os.path.basename(filename).split('-')
	nr_vcpus = int(tokens[2][0])
	bench_name = tokens[0] + "-" + tokens[1]
	bench_name = bench_name.replace("_", "-")

	model = HealthyStateModel.model_train(filename)
	actiDB.insert_model(bench_name, nr_vcpus, model)
