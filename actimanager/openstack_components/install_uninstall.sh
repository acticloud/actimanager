#!/bin/bash

case $1 in
install)
	echo "install"
	base_path=/home/jim/jimsiak/actimanager/openstack_components
	ln -s ${base_path}/filters/acticloud.py /usr/lib/python2.7/dist-packages/nova/scheduler/filters/
	ln -s ${base_path}/weights/acticloud.py /usr/lib/python2.7/dist-packages/nova/scheduler/weights/
	ln -s ${base_path}/weights/acticloud_calculate_profit.py /usr/lib/python2.7/dist-packages/nova/scheduler/weights/
	touch /etc/nova/nova.conf
	/etc/init.d/nova-scheduler restart
	;;
uninstall)
	echo "uninstall"
	rm /usr/lib/python2.7/dist-packages/nova/scheduler/filters/acticloud.py
	rm /usr/lib/python2.7/dist-packages/nova/scheduler/weights/acticloud.py
	rm /usr/lib/python2.7/dist-packages/nova/scheduler/weights/acticloud_calculate_profit.py
	touch /etc/nova/nova.conf
	/etc/init.d/nova-scheduler restart
	;;
*)
	echo "usage: $0 [ install | uninstall ]"
	;;
esac
