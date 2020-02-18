Initialize the actidb with the following steps:

'''
$ mysql -rUSER -p < acticlouddb_create.sql
... modify OPENSTACK_HOSTS in ../common/config.py ...
$ cd helper_scripts/
$ python insert_hosts_in_db.py
$ cd ..
$ python rabbitmq_client.py
'''
