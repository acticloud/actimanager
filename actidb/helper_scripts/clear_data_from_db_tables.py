import os, sys, json
sys.path.append('../')
from acticloudDB import ActiCloudDBClient

if (len(sys.argv) < 2):
	print "usage: %s [table_names]" % sys.argv[0]
	sys.exit(1)

actiDB = ActiCloudDBClient()

for tbl_name in sys.argv[1:]:
	if (actiDB.clear_data_from_table(tbl_name) == 1):
		print "Cleared all data from table:", tbl_name
	else:
		print "Could not clear table %s, probably it does not exist (available tables: %s)" % \
		                   (tbl_name, actiDB.get_db_table_names())
