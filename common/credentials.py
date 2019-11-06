import os
 
def get_nova_creds():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['password'] = os.environ['OS_PASSWORD']
    d['project_name'] = os.environ['OS_PROJECT_NAME']
    d['user_domain_name'] = os.environ['OS_USER_DOMAIN_NAME']
#    d['user_domain_id'] = os.environ['OS_USER_DOMAIN_ID']
    d['project_domain_name'] = os.environ['OS_PROJECT_DOMAIN_NAME']
#    d['project_domain_id'] = os.environ['OS_PROJECT_DOMAIN_ID']
    d['auth_url'] = os.environ['OS_AUTH_URL']
#   d['identity_api_version'] = os.environ['OS_IDENTITY_API_VERSION']
    return d
