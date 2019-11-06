#!/bin/bash

DELAY=30 # Delay between instructions

export SERVER_CREATE_GOLD="openstack server create --hint group=e942edc2-444e-4054-8632-9394d53432c4 --flavor demo-tiny --image cirros-new --nic none --availability-zone nova:compute-1"
export SERVER_CREATE_SILVER="openstack server create --hint group=ed5ac2ad-0e14-4260-8cd7-f0ddea410717 --flavor demo-tiny --image cirros-new --nic none --availability-zone nova:compute-1"
export SERVER_DELETE="openstack server delete"

export | grep "SERVER_"

echo '$SERVER_CREATE_GOLD gold-1'
$SERVER_CREATE_GOLD gold-1
sleep $DELAY

echo '$SERVER_CREATE_SILVER silver-1'
$SERVER_CREATE_SILVER silver-1
sleep $DELAY

echo '$SERVER_CREATE_GOLD gold-2'
$SERVER_CREATE_GOLD gold-2
sleep $DELAY

echo '$SERVER_CREATE_GOLD gold-3'
$SERVER_CREATE_GOLD gold-3
sleep $DELAY

echo '$SERVER_CREATE_GOLD gold-4'
$SERVER_CREATE_GOLD gold-4
sleep $DELAY

echo '$SERVER_CREATE_SILVER silver-2'
$SERVER_CREATE_SILVER silver-2
sleep $DELAY
echo '$SERVER_CREATE_SILVER silver-3'
$SERVER_CREATE_SILVER silver-3
sleep $DELAY
echo '$SERVER_CREATE_SILVER silver-4'
$SERVER_CREATE_SILVER silver-4
sleep $DELAY
echo '$SERVER_CREATE_SILVER silver-5'
$SERVER_CREATE_SILVER silver-5
sleep $DELAY
echo '$SERVER_CREATE_SILVER silver-6'
$SERVER_CREATE_SILVER silver-6
sleep $DELAY
echo '$SERVER_CREATE_SILVER silver-7'
$SERVER_CREATE_SILVER silver-7
sleep $DELAY
echo '$SERVER_CREATE_SILVER silver-8'
$SERVER_CREATE_SILVER silver-8
sleep $DELAY


echo '$SERVER_CREATE_GOLD gold-5'
$SERVER_CREATE_GOLD gold-5
sleep $DELAY
echo '$SERVER_DELETE gold-5'
$SERVER_DELETE gold-5
sleep $DELAY
echo '$SERVER_CREATE_GOLD gold-5'
$SERVER_CREATE_GOLD gold-5
sleep $DELAY
