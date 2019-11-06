# Copyright (c) 2011-2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as logging

from nova.scheduler import filters

LOG = logging.getLogger(__name__)

class ActicloudLabFilter(filters.BaseHostFilter):
    """
    ACTiCLOUD Lab filter.
    Part of ACTiManager external.
    Reads a tag with key 'tolab', and if this is set to true filters out all
    non-lab hosts.
    """

    # the hosts that are labs
    lab_hosts = [ "compute3.ntua.gr" ]

    # the UUIDs of the  VMs that have been placed in the lab and are ready to go to production
    vm_ready_from_production = []
    calls = 0

    # list of hosts doesn't change within a request
    run_filter_once_per_request = True

    def _vm_ready_for_production(self, uuid):
        return uuid in self.vm_ready_from_production

    def _host_is_lab(self, hostname):
        return hostname in self.lab_hosts

    def host_passes(self, host_state, spec_obj):
        ret = False
        uuid = spec_obj.instance_uuid
        ready_for_production = self._vm_ready_for_production(uuid)
        host_is_lab = self._host_is_lab(host_state.nodename)
        LOG.warning("Executing acticloud_lab_filter for host %(host)s uuid %(uuid)s %(rdy)d", {'host': host_state.nodename, 'uuid': uuid, 'rdy': ready_for_production})

        if ( ((ready_for_production) and (not host_is_lab)) or \
             ((not ready_for_production) and (host_is_lab)) ):
            ret = True

        self.calls += 1
        if (self.calls == 3):
            self.vm_ready_from_production.append(uuid)

        return ret
