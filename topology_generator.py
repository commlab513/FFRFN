#!/usr/bin/python3

# Ip subnet allocation in Testbed:
#   172.x.x.x/8 = Routers OSPF ip subnet
#   100.x.x.x/8 = Fibbing private ip subnet
#   192.x.x.x/8 = fibbing fake routers ip subnet
#   142.x.x.x/8 = Users ip subnet
#   140.x.x.x/8 = Monitoring cycle packets ip subnet (source)
#   150.x.x.x/8 = Monitoring cycle packets ip subnet (destination)

# Notice: 
#   Line 56-63: GNS3 cluster information, 
#   Line 193: Interfaces connected to GNS3 Topology (Depends on the configurations of GNS3-Cluster-1)
#   CONF_TYPE: <NORMAL, BFD, FH>, types of the cisco configurations

import requests
import json
import os,sys
import paramiko
# GNS3 Cluster Server IP
GNS3_Main_Server = '172.16.22.101:3080'
FILE_DIRECTION = os.getcwd()
CONF_TYPE = "BFD"

class Topology:
    def __init__(self, file):
        self.file = file
        self.node_count = 0
        self.project_id = None
        self.nodes = {}
        self.router_2_rotuer_link_set = {}
        self.traffic_2_rotuer_link_set = {}
        self.real_port_2_rotuer_link_set = {}
        self.topology = []
        self.consoles = ""
        self.port_count = {}
        self.GNS3_Remote = { }

    def create(self, txt_file):
        data = txt_file.read().split('\n')
        self.node_count = int(data.pop(0))
        
        for i in range(self.node_count):
            links = data[i].split(' ')
            links.pop(-1)
            for l in range(len(links)):
                links[l] = int(links[l])
            self.topology.append(links)
        
def main ():
    files = os.listdir(FILE_DIRECTION+'/topology')
    for file in files:
        if '.txt' in file and len(file.split("_"))==3:
            payload = {'name':'%s'%file.split('.')[0]}
            response = requests.post('http://%s/v2/projects'%(GNS3_Main_Server), params=payload)
            if response.status_code == 409:
                print ("GNS3 Topology:%s existde, skip. "%file.split('.')[0])
                pass
            else:
                os.chdir(FILE_DIRECTION+'/topology')
                topology = Topology(file)
                topology.GNS3_Remote = {  # host ip <--> Compute_id, cpu core 8*
                    'local':{'ip':'172.16.22.101','core':7, 'ram':16384, 'compute_id':'local'},
                    'gns3vm-2':{'ip':'172.16.22.102','core':7, 'ram':16384, 'compute_id':'gns3vm-2'},
                    'gns3vm-3':{'ip':'172.16.22.103','core':7, 'ram':16384, 'compute_id':'gns3vm-3'},
                    'gns3vm-4':{'ip':'172.16.22.104','core':7, 'ram':16384, 'compute_id':'gns3vm-4'},
                    'gns3vm-5':{'ip':'172.16.22.105','core':7, 'ram':16384, 'compute_id':'gns3vm-5'},
                    'gns3vm-6':{'ip':'172.16.22.106','core':7, 'ram':16384, 'compute_id':'gns3vm-6'},
                }
                txt_file = open(topology.file, 'r')
                topology.create(txt_file)
                txt_file.close()
                info = response.json()
                topology.project_id = info['project_id']
                print ("Generating GNS3 Topology:%s"%file.split('.')[0])
                project_folder = FILE_DIRECTION+"/projects/"+file[0:-4]
                os.system("rm -rf "+project_folder)
                os.system("mkdir "+project_folder)
                os.chdir(project_folder)
                for n in range(topology.node_count):
                    temp_GNS3_Remote = dict(topology.GNS3_Remote)
                    del temp_GNS3_Remote['local']
                    if n == 0 or n==4:
                        remote = 'local'
                    else:
                        remote = max(temp_GNS3_Remote, key=lambda x:temp_GNS3_Remote[x]['core'])
                    payload = {
                        "name": "Router-%02d"%(n+1), 
                        "node_type": "qemu", 
                        "compute_id": topology.GNS3_Remote[remote]['compute_id'],
                        "console_type":"telnet",
                        "properties":{
                            "hda_disk_image": "csr1000v-universalk9.16.08.01a-serial.qcow2",
                            "name": "Router-%02d"%(n+1),
                            "qemu_path": "/usr/bin/qemu-system-x86_64",
                            "cpus":1,
                            "ram": 3072,
                            "adapters": 16,
                            "adapter_type": "vmxnet3",
                            "platform": "x86_64"
                        }
                    }
                    response = requests.post('http://%s/v2/projects/%s/nodes'%(GNS3_Main_Server, topology.project_id), json=payload)
                    info = response.json()
                    #print (json.dumps(info, sort_keys=True,indent=4, separators=(',', ': ')))
                    topology.nodes.setdefault(n,{'node_id':info['node_id'], 'ports':info['ports'], 'compute_id':info['compute_id'], 'GNS3Node':remote})
                    topology.GNS3_Remote[remote]['core'] -= 1
                    topology.GNS3_Remote[remote]['ram'] -= 3072

                for remote in topology.GNS3_Remote:
                    topology.port_count.setdefault(remote,0)
                    topology.traffic_2_rotuer_link_set.setdefault(remote,{})
                for n in topology.nodes:
                    remote = topology.nodes[n]['GNS3Node']
                    topology.traffic_2_rotuer_link_set[remote].setdefault(n,[])
                    payload = {
                        "name": "NAT-%02d"%(n+1), 
                        "node_type": "nat", 
                        "compute_id": topology.GNS3_Remote[remote]['compute_id']
                    }
                    response = requests.post('http://%s/v2/projects/%s/nodes'%(GNS3_Main_Server, topology.project_id), json=payload)
                    nat = response.json()
                    payload = {
                        "name": "Host-%02d"%(n+1), 
                        "node_type": "docker", 
                        "compute_id": topology.GNS3_Remote[remote]['compute_id'],
                        "console_type":"telnet",
                        "properties":{
                            "image":"mountainshan/tester",
                            "name":"Host-%02d"%(n+1),
                            "adapters":2,
                            "start_command":"bash"
                        }
                    }
                    response = requests.post('http://%s/v2/projects/%s/nodes'%(GNS3_Main_Server, topology.project_id), json=payload)
                    docker = response.json()
                    node_directory = docker['node_directory']
                    container_id = docker['properties']['container_id']
                    payload = {
                        "nodes": [
                            {
                                "node_id": docker['node_id'],
                                "adapter_number": docker['ports'][0]['adapter_number'],
                                "port_number": docker['ports'][0]['port_number']
                            }, 
                            {
                                "node_id": topology.nodes[n]['node_id'],
                                "adapter_number": topology.nodes[n]['ports'][-1]['adapter_number'],
                                "port_number":topology.nodes[n]['ports'][-1]['port_number']
                            }
                        ]
                    }
                    response = requests.post('http://%s/v2/projects/%s/links'%(GNS3_Main_Server, topology.project_id), json=payload)
                    info = response.json()
                    topology.traffic_2_rotuer_link_set[remote][n].append("%s_%d_%s"%(container_id,topology.nodes[n]['ports'][-1]['adapter_number']+1,node_directory))
                    topology.nodes[n]["ports"].pop(-1)
                    topology.port_count[remote]+=1
                    payload = {
                        "nodes": [
                            {
                                "node_id": docker['node_id'],
                                "adapter_number": docker['ports'][1]['adapter_number'],
                                "port_number": docker['ports'][1]['port_number']
                            }, 
                            {
                                "node_id": nat['node_id'],
                                "adapter_number": nat['ports'][0]['adapter_number'],
                                "port_number":nat['ports'][0]['port_number']
                            }
                        ]
                    }
                    response = requests.post('http://%s/v2/projects/%s/links'%(GNS3_Main_Server, topology.project_id), json=payload)
                    info = response.json()
                
                remote = max(topology.GNS3_Remote, key=lambda x:topology.GNS3_Remote[x]['core'])
                payload = {
                    "name": "Router-%02d"%(99), 
                    "node_type": "qemu", 
                    "compute_id": topology.GNS3_Remote[remote]['compute_id'],
                    "console_type":"telnet",
                    "properties":{
                        "hda_disk_image": "csr1000v-universalk9.16.08.01a-serial.qcow2",
                        "name": "Router-%02d"%(99),
                        "qemu_path": "/usr/bin/qemu-system-x86_64",
                        "cpus":1,
                        "ram": 3072,
                        "adapters": 16,
                        "adapter_type": "vmxnet3",
                        "platform": "x86_64"
                    }
                }
                response = requests.post('http://%s/v2/projects/%s/nodes'%(GNS3_Main_Server, topology.project_id), json=payload)
                info = response.json()
                topology.nodes.setdefault(99,{'node_id':info['node_id'], 'ports':info['ports'], 'compute_id':info['compute_id'], 'GNS3Node':remote})
                topology.GNS3_Remote[remote]['core'] -= 1
                topology.GNS3_Remote[remote]['ram'] -= 3072
                for i,n in zip(['br-enp2s0','br-enp9s0','enp7s0-veth7','enp7s0-veth5','enp7s0-veth3','enp7s0-veth1','enp8s0-veth7','enp8s0-veth5','enp8s0-veth3','enp8s0-veth1'], [0,99,0,0,0,0,4,4,4,4]):
                    payload = {
                        "name":"RealPort-%s"%(i),
                        "node_type":"cloud",
                        "compute_id":topology.GNS3_Remote['local']['compute_id'],
                        "properties":{
                            "interfaces":[ { "name": i, "special": True, "type": "ethernet" } ],
                            "ports_mapping":[ { "interface": i, "name": i, "port_number": 0, "type": "ethernet" } ]
                        }
                    }
                    response = requests.post('http://%s/v2/projects/%s/nodes'%(GNS3_Main_Server, topology.project_id), json=payload)
                    info = response.json()
                    payload = {
                        "nodes": [
                            {
                                "node_id": info['node_id'],
                                "adapter_number": info['ports'][0]['adapter_number'],
                                "port_number": 0
                            }, 
                            {
                                "node_id": topology.nodes[n]['node_id'],
                                "adapter_number": topology.nodes[n]['ports'][-1]['adapter_number'],
                                "port_number":0
                            }
                        ]
                    }
                    response = requests.post('http://%s/v2/projects/%s/links'%(GNS3_Main_Server, topology.project_id), json=payload)
                    info = response.json()
                    topology.real_port_2_rotuer_link_set.setdefault(n, "%s_%d"%(i,topology.nodes[n]['ports'][-1]['adapter_number']+1))
                    topology.nodes[n]["ports"].pop(-1)
                topology_to_txt = open("link_list_info.txt", "w")
                for i in range(len(topology.topology)):
                    for j in range(len(topology.topology[i])):
                        if (topology.topology[i][j] > 0 and "%d_%d"%(j,i) not in topology.router_2_rotuer_link_set):
                            payload = {
                                "nodes": [
                                    {
                                        "node_id": topology.nodes[i]['node_id'],
                                        "adapter_number": topology.nodes[i]['ports'][0]['adapter_number'],
                                        "port_number":0
                                    }, 
                                    {
                                        "node_id": topology.nodes[j]['node_id'],
                                        "adapter_number": topology.nodes[j]['ports'][0]['adapter_number'],
                                        "port_number":0
                                    }
                                ]
                            }
                            response = requests.post('http://%s/v2/projects/%s/links'%(GNS3_Main_Server, topology.project_id), json=payload)
                            info = response.json()
                            if (response.status_code == 201):
                                topology.router_2_rotuer_link_set.setdefault("%d_%d"%(i,j),"%d_%d"%(topology.nodes[i]['ports'][0]['adapter_number']+1,topology.nodes[j]['ports'][0]['adapter_number']+1))
                                topology_to_txt.write("%d %d %s\n"%(i,j,info['link_id']))
                                topology.nodes[i]["ports"].pop(0)
                                topology.nodes[j]["ports"].pop(0)
                topology_to_txt.close()
                response = requests.post('http://%s/v2/projects/%s/close'%(GNS3_Main_Server, topology.project_id))
                info = response.json()
                node_config = []
                network_config = []
                backup_router_ip_config = open("backup_ip_address.txt", "w")
                for i in range(topology.node_count):
                    node_config.append(open("R%d.cfg"%(i+1), "w"))
                    network_config.append("")
                    node_config[i].write("interface Loopback 1\nip address %d.%d.%d.%d 255.255.255.255\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nexit\n\n"%(i+1,i+1,i+1,i+1))
                    network_config[i]+="network %d.%d.%d.%d 0.0.0.0 area 0\n"%(i+1,i+1,i+1,i+1)
                ip_subnet = 1
                for i in topology.router_2_rotuer_link_set:
                    ip_subnet_class_b = ip_subnet%254
                    ip_subnet_class_c = int(ip_subnet/254)
                    src,dst = i.split("_")
                    src_port,dst_port = topology.router_2_rotuer_link_set[i].split("_")
                    src = int(src)
                    dst = int(dst)
                    if CONF_TYPE=="BFD":
                        node_config[src].write("interface GigabitEthernet %s\nip address 172.%d.%d.1 255.255.255.0\nip address 100.%d.%d.1 255.255.255.0 secondary\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nbfd interval 50 min_rx 50 multiplier 3\nexit\n\n"%(src_port, ip_subnet_class_b, ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                        node_config[dst].write("interface GigabitEthernet %s\nip address 172.%d.%d.2 255.255.255.0\nip address 100.%d.%d.2 255.255.255.0 secondary\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nbfd interval 50 min_rx 50 multiplier 3\nexit\n\n"%(dst_port, ip_subnet_class_b, ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                    elif CONF_TYPE=="FH":
                        node_config[src].write("interface GigabitEthernet %s\nip address 172.%d.%d.1 255.255.255.0\nip address 100.%d.%d.1 255.255.255.0 secondary\nip ospf dead-interval minimal hello-multiplier 5\nno shutdown\nexit\n\n"%(src_port, ip_subnet_class_b, ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                        node_config[dst].write("interface GigabitEthernet %s\nip address 172.%d.%d.2 255.255.255.0\nip address 100.%d.%d.2 255.255.255.0 secondary\nip ospf dead-interval minimal hello-multiplier 5\nno shutdown\nexit\n\n"%(dst_port, ip_subnet_class_b, ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                    else:
                        node_config[src].write("interface GigabitEthernet %s\nip address 172.%d.%d.1 255.255.255.0\nip address 100.%d.%d.1 255.255.255.0 secondary\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nexit\n\n"%(src_port, ip_subnet_class_b, ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                        node_config[dst].write("interface GigabitEthernet %s\nip address 172.%d.%d.2 255.255.255.0\nip address 100.%d.%d.2 255.255.255.0 secondary\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nexit\n\n"%(dst_port, ip_subnet_class_b, ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                    network_config[src]+="network 172.%d.%d.0 255.255.255.0 area 0\n"%(ip_subnet_class_b, ip_subnet_class_c)
                    network_config[src]+="network 100.%d.%d.0 255.255.255.0 area 0\n"%(ip_subnet_class_b, ip_subnet_class_c)
                    network_config[dst]+="network 172.%d.%d.0 255.255.255.0 area 0\n"%(ip_subnet_class_b, ip_subnet_class_c)
                    network_config[dst]+="network 100.%d.%d.0 255.255.255.0 area 0\n"%(ip_subnet_class_b, ip_subnet_class_c)
                    backup_router_ip_config.write("%d %d 100.%d.%d.1 100.%d.%d.2\n"%(src, dst, ip_subnet_class_b,ip_subnet_class_c,ip_subnet_class_b,ip_subnet_class_c))
                    ip_subnet += 1
                backup_router_ip_config.close()
                router99 = open("R99.cfg","w")
                if CONF_TYPE == "BFD":
                    router99.write("interface Loopback 1\nip address 99.99.99.99 255.255.255.255\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nexit\n\n")
                    router99.write("interface GigabitEthernet 16\nmac-address aa:bb.ccdd.ee02\nip address 192.0.0.1 255.255.255.0\nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nexit\n\n")
                else:
                    router99.write("interface Loopback 1\nip address 99.99.99.99 255.255.255.255\nip ospf dead-interval minimal hello-multiplier 5\nno shutdown\nexit\n\n")
                    router99.write("interface GigabitEthernet 16\nmac-address aa:bb.ccdd.ee02\nip address 192.0.0.1 255.255.255.0\nip ospf dead-interval minimal hello-multiplier 5\nno shutdown\nexit\n\n")
                router99.write("router ospf 1\n")
                router99.write("router-id 99.99.99.99\ntimer pacing flood 5\nredistribute connected metric 1000 metric-type 1 subnets\n")
                router99.write("network 99.99.99.99 255.255.255.255 area 0\n")
                router99.write("network 192.0.0.0 255.255.0.0 area 0\n")
                router99.write("distribute-list 1 in\nexit\n\n")
                router99.close()               
                
                if CONF_TYPE == "BFD":
                    node_config[0].write("interface GigabitEthernet 15\nmac-address aa:bb.ccdd.ee02\nip address 192.0.0.2 255.255.255.0 \nip ospf hello-interval 5\nip ospf dead-interval 40\nno shutdown\nexit\n\n")
                else:
                    node_config[0].write("interface GigabitEthernet 15\nmac-address aa:bb.ccdd.ee02\nip address 192.0.0.2 255.255.255.0 \nip ospf dead-interval minimal hello-multiplier 5\nno shutdown\nexit\n\n")
                network_config[0]+="network 192.0.0.0 255.255.255.0 area 0\n"
                
                node_config[0].write("interface GigabitEthernet 11\nip address 141.0.0.254 255.255.255.0\nmac-address 1a2b.3c4d.5161\nno shutdown\nexit\n\n")
                node_config[0].write("interface GigabitEthernet 12\nip address 141.0.1.254 255.255.255.0\nmac-address 1a2b.3c4d.5162\nno shutdown\nexit\n\n")
                node_config[0].write("interface GigabitEthernet 13\nip address 141.0.2.254 255.255.255.0\nmac-address 1a2b.3c4d.5163\nno shutdown\nexit\n\n")
                node_config[0].write("interface GigabitEthernet 14\nip address 141.0.3.254 255.255.255.0\nmac-address 1a2b.3c4d.5164\nno shutdown\nexit\n\n")
                node_config[4].write("interface GigabitEthernet 12\nip address 151.0.0.254 255.255.255.0\nmac-address 1a2b.3c4d.5261\nno shutdown\nexit\n\n")
                node_config[4].write("interface GigabitEthernet 13\nip address 151.0.1.254 255.255.255.0\nmac-address 1a2b.3c4d.5262\nno shutdown\nexit\n\n")
                node_config[4].write("interface GigabitEthernet 14\nip address 151.0.2.254 255.255.255.0\nmac-address 1a2b.3c4d.5263\nno shutdown\nexit\n\n")
                node_config[4].write("interface GigabitEthernet 15\nip address 151.0.3.254 255.255.255.0\nmac-address 1a2b.3c4d.5264\nno shutdown\nexit\n\n")

                for remote in topology.traffic_2_rotuer_link_set:
                    for router in topology.traffic_2_rotuer_link_set[remote]:
                        node_config[router].write("interface GigabitEthernet 16\nip address 142.%d.0.1 255.255.255.0\nno shutdown\nexit\n\n"%(router+1))
                
                for i in range(topology.node_count):
                    node_config[i].write("router ospf 1\n")
                    node_config[i].write("router-id %d.%d.%d.%d\ntimer pacing flood 5\nredistribute connected metric 1000 metric-type 1 subnets\n"%(i+1,i+1,i+1,i+1))
                    node_config[i].write(network_config[i])
                    node_config[i].write("distribute-list 1 in\n")
                    if CONF_TYPE == "BFD":
                        node_config[i].write("bfd all-interfaces\nexit\n\n")
                    else:
                        node_config[i].write("exit\n\n")
                    node_config[i].write("access-list 1 deny 100.0.0.0 0.255.255.255\naccess-list 1 permit any\n")
                    node_config[i].write("exit\n")
                    node_config[i].close()

if '__main__' == __name__:
    main()
    