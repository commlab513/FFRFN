import requests
import json
import os,sys
from telnetlib import Telnet 
import time
import threading
import paramiko
# GNS3 Server IP and API address
GNS3_Main_IP = '172.16.22.101'
GNS3_Main_Server = '172.16.22.101:3080'
FILE_DIRECTION = os.getcwd()

class Configurator:
    def __init__(self, topology):
        os.chdir(FILE_DIRECTION+'/projects/'+topology)
        self.topology = topology
        return
    
    def get_topology_info(self): 
        response = requests.get("http://%s/v2/projects"%(GNS3_Main_Server))
        info = response.json()
        for i in (info):
            if self.topology in i['filename']:
                self.project_id = i['project_id']
                break
        response = requests.post('http://%s/v2/projects/%s/open'%(GNS3_Main_Server, self.project_id))
        response = requests.get("http://%s/v2/projects/%s/nodes"%(GNS3_Main_Server, self.project_id))
        self.information = response.json()

    def router_telnet_process(self, node, name, console_host, console):
        os.chdir(FILE_DIRECTION+'/projects/'+self.topology)
        self.start_gns3(node, name)
        #print("Configuring %s ..."%(name))
        config_file = open("R%d.cfg"%(int(name.split("-")[-1])), "r")
        command = config_file.read().split('\n')
        telnet_connect=Telnet(console_host, str(console))
        telnet_connect.read_until(b"Would you like to enter the initial configuration dialog? [yes/no]:", timeout=5*60)
        telnet_connect.write("no".encode('ascii') + b"\r\n")
        telnet_connect.write(b"\r\n")
        #telnet_connect.set_debuglevel(2)
        time.sleep(60)
        telnet_connect.write(b"\r\n")
        telnet_connect.read_until(b"Router>")
        telnet_connect.write("enable".encode('ascii')+b"\r\n")
        telnet_connect.write("configure terminal".encode('ascii')+b"\r\n")
        for c in command:
            telnet_connect.write(c.encode('ascii')+b"\r\n")
            time.sleep(0.2)
        telnet_connect.close()
        sys.stdout.flush()
        ###print("%s configuration done."%(name))

    def host_telnet_process(self, node, name, console_host, console):
        self.start_gns3(node, name)
        #print("Configuring %s ..."%(name))
        telnet_connect=Telnet(console_host, str(console))
        #telnet_connect.set_debuglevel(2)
        telnet_connect.write(b"\r\n")
        telnet_connect.write(("ifconfig eth0 142.%d.0.2/24"%(int(name.split("-")[-1]))).encode('ascii') + b"\r\n")
        time.sleep(0.2)
        telnet_connect.write(("ifconfig eth1 192.168.122.%d/24"%(int(name.split("-")[-1])+100)).encode('ascii') + b"\r\n")
        time.sleep(0.2)
        telnet_connect.write(("route add -net 142.0.0.0/8 gw 142.%d.0.1 dev eth0"%(int(name.split("-")[-1]))).encode('ascii') + b"\r\n")
        time.sleep(0.2)
        telnet_connect.write(("route add default gw 192.168.122.1 dev eth1").encode('ascii') + b"\r\n")
        time.sleep(0.2)
        telnet_connect.close()
        sys.stdout.flush()

    def start_gns3(self, node, name):
        ##print("Starting node %s ..."%name)
        response = requests.post("http://%s/v2/projects/%s/nodes/%s/start"%(GNS3_Main_Server, self.project_id, node), json={})

    def stop_gns3(self, node, name):
        ##print("Stopping node %s ..."%name)
        response = requests.post("http://%s/v2/projects/%s/nodes/%s/stop"%(GNS3_Main_Server, self.project_id, node),json={})
    
    def auto_idle_pc(self, node):
        response = requests.post("http://%s/v2/projects/%s/nodes/%s/dynamips/auto_idlepc"%(GNS3_Main_Server, self.project_id, node))
    
    def reset_router_resource_usage(self):
        threads = []
        for i in (self.information):
            if ('Router' in i['name']):
                threads.append(threading.Thread(target=self.auto_idle_pc, args=(i['node_id'],)))
                threads[-1].start()
        for t in threads:
            t.join()
    
    def start_topology(self):  
        threads = []
        for i in (self.information):
            if (i['console_host'] == "0.0.0.0"):
                console_host = GNS3_Main_IP
            else:
                console_host = i['console_host']
            if ('Router' in i['name']):
                threads.append(threading.Thread(target=self.router_telnet_process, args=(i['node_id'],i['name'],console_host,i['console'],)))
                threads[-1].start()
            elif ('Host' in i['name']):
                self.host_telnet_process(i['node_id'],i['name'],console_host,i['console'])
        for t in threads:
            t.join()
        print("All Router configured, waiting 120s for OSPF")
        time.sleep(120)
    
    def stop_topology(self):  
        threads = []
        for i in (self.information):
            if (i['console_host'] == "0.0.0.0"):
                    console_host = GNS3_Main_IP
            else:
                console_host = i['console_host']
            if ('Router' in i['name']):
                threads.append(threading.Thread(target=self.stop_gns3,args=(i['node_id'],i['name'],)))
                threads[-1].start()
            elif ('Host' in i['name']):
                threads.append(threading.Thread(target=self.stop_gns3, args=(i['node_id'],i['name'],)))
                threads[-1].start()
        for t in threads:
            t.join()
        response = requests.post('http://%s/v2/projects/%s/close'%(GNS3_Main_Server, self.project_id))
