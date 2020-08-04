#!/bin/bash

# Experiment type: 
# Fibbing_Only = Using original failure dectection (ex. BFD, OSPF Fast Hello Message, etc. )
# Packet_Detection = Using our method
exp_case="Fibbing_Only"

# Interfaces for Fibbing Controllers
# Example: 
#  enp1s0 = Interface for monitoring cycle sender
#  enp2s0 = Interface for cycle receiver
#  enp3s0 = Interface for Router R1
#  enp7s0 = Interface for Router R99
INTERFACES="enp1s0 enp2s0 enp3s0 enp7s0 "

# Counts for the each test
count=20

# Random seed
RANDOM=20

# Topology Name (Can more than one )
topos="10_04_01 "

# GNS3 Cluster IPs
GNS3_IPs="172.16.22.101 172.16.22.102 172.16.22.103 172.16.22.104 172.16.22.105 172.16.22.106 "

# Disable interfaces offloading
for INTF in $INTERFACES; do
    TOE_OPTIONS="rx tx sg tso ufo gso gro lro rxvlan txvlan rxhash"
    for TOE_OPTION in $TOE_OPTIONS; do
        /sbin/ethtool --offload "$INTF" "$TOE_OPTION" off
    done
    sysctl net.ipv6.conf.$INTF.disable_ipv6=1
    ifconfig $INTF promisc
done

# Start GNS3 Service
echo "$(date), GNS3 starting."
for ip in $GNS3_IPs; do
    sshpass -p gns3 ssh gns3@ "echo \"gns3\" | sudo gns3server --daemon" > /dev/null 2>&1 &
done
sleep 15

# Testing start
for topo in $topos
do
    seed=$RANDOM
    echo "$(date), Topology $topo, experiment start, seed: $seed, count: $count"
    sudo python3 ./fibbing_controller.py $exp_case $topo $seed $count $INTERFACES
    echo "$(date), Topology $topo, experiment finish, sleep 120s "
    sleep 60
done

# Stop GNS3 Service
for ip in $GNS3_IPs; do
    sshpass -p gns3 ssh gns3@ "echo \"gns3\" | sudo pkill -f gns3server" > /dev/null 2>&1 &
done
echo "$(date), GNS3 Stopped."
echo "$(date), Exit."
