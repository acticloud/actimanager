import os, sys
sys.path.append('../')
sys.path.append('../../common')
from acticloudDB import ActiCloudDBClient
from config import *

actiDB = ActiCloudDBClient()

for host in OPENSTACK_HOSTS:
	actiDB.insert_host(host)

#for filename in sys.argv[1:]:
#	tokens = os.path.basename(filename).split('-')
#	nr_vcpus = int(tokens[2][0])
#	bench_name = tokens[0] + "-" + tokens[1]
#	bench_name = bench_name.replace("_", "-")
#
#	model = HealthyStateModel.model_train(filename)
#	actiDB.insert_model(bench_name, nr_vcpus, model)
