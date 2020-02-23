#!/usr/bin/env python2.7

import logging
import libvirt
import subprocess


class LibVirtConnection(object):
    def __init__(self, node, hypervisor):
        self.node = node
        self.hypervisor = hypervisor
        self._conn = None

    def connect(self):
        # XXX: Probably qemu-specific / not generic
        conn_uri = self.hypervisor + "://" + self.node + "/system"
        self._conn = libvirt.open(conn_uri)
        if self._conn is None:
            logging.error("Failed to connect to %s".format(conn_uri))

        return self._conn

    def close(self):
        self._conn.close()

    def __enter__(self):
        self.connect()
        return self._conn

    def __exit__(self, type, value, traceback):
        self._conn.close()


class LibVirtNode(object):
    def __init__(self, conn):
        self._conn = conn

    def get_node_cpus(self):
        return self._conn.getCPUMap()

    def get_node_mapping(self):
        conn = self._conn

        cpumap = [None] * conn.getCPUMap()[0]
        for domid in conn.listDomainIDs():
            d = conn.lookupByID(domid)
            vcpumap = d.vcpuPinInfo()
            for i, v in enumerate(vcpumap):
                for j, p in enumerate(v):
                    if p:
                        if cpumap[j] is None:
                            cpumap[j] = [(d.ID(), i)]
                        else:
                            cpumap[j].append((d.ID(), i))

        return cpumap

    def get_node_info(self):
        nodeinfo = self._conn.getInfo()
        print nodeinfo
        print('Model: ' + str(nodeinfo[0]))
        print('Memory size: ' + str(nodeinfo[1]) + "MB")
        print('Number of CPUs: ' + str(nodeinfo[2]))
        print('MHz of CPUs: ' + str(nodeinfo[3]))
        print('Number of NUMA nodes: ' + str(nodeinfo[4]))
        print('Number of CPU sockets: ' + str(nodeinfo[5]))
        print('Number of CPU cores per socket: ' + str(nodeinfo[6]))
        print('Number of CPU threads per core: ' + str(nodeinfo[7]))
        return nodeinfo


class LibVirtInstance(object):
    def __init__(self, conn, instance_id):
        self._conn = conn
        self._libvirt_domain = None
        if (isinstance(instance_id, int)):
            self._libvirt_domain = conn.lookupByID(instance_id)
        elif (isinstance(instance_id, str)):
            self._libvirt_domain = conn.lookupByName(instance_id)
        self.instance_id = instance_id

    def map_instance_vcpu(self, vcpu, pcpus):
        cpumap = [False] * self._conn.getCPUMap()[0]
        for p in pcpus:
            cpumap[p] = True

        return self._libvirt_domain.pinVcpu(vcpu, tuple(cpumap))

    def get_instance_mapping(self):
        return self._libvirt_domain.vcpuPinInfo()

    def attach_device(self, xml):
	# FIXME: This used to be a Python API call. Switched to virsh to debug
	# the hotplug issues. Now that these are resolved, this could revert
	# back to the Python API.
	subprocess.call("virsh attach-device --domain %s --live ./user-net.xml" % self._libvirt_domain.ID(), shell=True)

def main(argv):
    if (len(argv) < 2):
        print "usage: " + argv[0] + " [id=<instance_id> | name=<instance_name>]"
        sys.exit(1)

    id_or_name_label = sys.argv[1].split("=")[0]
    id_or_name = sys.argv[1].split("=")[1]
    if (id_or_name_label == "id"):
        id_or_name = int(id_or_name)

    print "Lookup up by " + id_or_name_label, id_or_name
    with LibVirtConnection("", "qemu") as libvconn:
        libvinstance = LibVirtInstance(libvconn, id_or_name)
#       libvinstance.map_instance_vcpu(0, [0])
        print libvinstance.get_instance_mapping()
    
        print "Node Info:"
        libvnode = LibVirtNode(libvconn)
        libvnode.get_node_info()


import sys
if __name__ == '__main__':
    main(sys.argv)
