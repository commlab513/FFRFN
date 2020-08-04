# A Fast Failure Recovery Scheme for Fibbing Networks GNS3 Testbed 
---
This repo is for building a GNS3 Testbed from **A Fast Failure Recovery Scheme for Fibbing Networks**. 
System requirement: 
* Hardware:
    * CPU: Intel i7 serise 
    * RAM: 16 GB 
    * Physical interfaces: 4
* Software: 
    * OS: Ubuntu 16.04.6 
    * GNS3 Version: 2.1.21
    * Python version: 2.7.17

---

## Installation:
### Controller
1. Install tools via apt: **sudo apt install python3 python3-pip**
2. Install tools via pip3: **sudo pip3 install scapy netifaces requests paramiko**
### GNS3 Server
1. Install GNS3 remote server: (website: https://docs.gns3.com/docs/getting-started/installation/remote-server)
    > sudo su;
    > cd /tmp;
    > wget -c https://raw.githubusercontent.com/GNS3/gns3-server/master/scripts/remote-install.sh -O gns3-remote-install.sh;
    > **(Notice that please comment line 153-157 before running install script. )**
    > bash gns3-remote-install.sh --with-iou --with-i386-repository;
2. Install tools via apt: **sudo apt install bridge-utils**
3. if you are configuring GNS3 remote server 1, you must copy viface_config.sh to /etc/network/if_up.d, And than configuring the shell script with permission 600
---
## Configuring testbed
1. Configuring GNS3 remote servers as a cluster
2. Insert router image to GNS3 cluster
3. Run the python script **topology_generator.py** to build GNS3 project. 
4. Using script **run_test.sh** to start the test.