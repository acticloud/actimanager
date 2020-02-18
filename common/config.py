## The set of compute nodes
## Each entry is of the form (name, nvcpus, RAM (GB), is_lab)
OPENSTACK_HOSTS = [ ("acticloud1", 20, 256, 1), ("acticloud2", 20, 256, 0),
                    ("acticloud3", 20, 256, 0), ("acticloud4", 20, 256, 0) ]

## Credentials to access the acticloud MySQL database
ACTICLOUDDB_HOSTNAME = "localhost"
ACTICLOUDDB_USERNAME = "root"
ACTICLOUDDB_PASSWORD = "CHANGEME"
ACTICLOUDDB_DBNAME = "acticloudDB" 

## Credentials for the rabbitmq queue that is used for the communication
## between ACTiManager.internal and ACTiManager.external
RABBITMQ_IP = "10.0.0.8"
RABBITMQ_USERNAME = "openstack"
RABBITMQ_PASSWORD = "CHANGEME"
RABBITMQ_ACTI_QUEUE_NAME = "acti_queue"

## Credentials for Openstack's rabbitmq messaging service
RABBITMQ_BROKER_URI="amqp://" + RABBITMQ_USERNAME + ":" + RABBITMQ_PASSWORD + "@controller:5672//"
EXCHANGE_NAME = "nova"
ROUTING_KEY = "notifications.info"
QUEUE_NAME = "nova_dump_queue"

## Openstack credentials
## FIXME(jimsiak): is it fine with our OCDs to have a function here?
def get_nova_creds():
	d = {}
	d['username'] = "admin"
	d['password'] = "CHANGEME"
	d['project_name'] = "admin"
	d['user_domain_name'] = "Default"
	d['project_domain_name'] = "Default"
	d['auth_url'] = "http://controller:35357/v3"
	return d
