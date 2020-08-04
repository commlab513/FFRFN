import socket
import time
import sys,os
import requests
import json
import threading
import select
from telnetlib import Telnet 
# GNS3 Cluster Server
GNS3_Main_Server = '172.16.22.101:3080'

class Packet_Controller:
    def __init__(self, topology, suspend=None):
        self.topology = topology
        self.reads = []
        self.filename = '%s_%s.csv'%(topology,time.strftime("%Y%m%d-%H%M%S",time.localtime()))
        os.chdir(os.getcwd()+'/projects/'+topology)
        self.links = {}
        file = open("link_list_info.txt",'r')
        data = file.read().split('\n')
        data.pop(-1)
        for d in data:
            l = d.split(' ')
            self.links.setdefault("%s,%s"%(l[0],l[1]), l[2])
        file.close()
        response = requests.get("http://%s/v2/projects"%(GNS3_Main_Server))
        info = response.json()
        for i in (info):
            if topology in i['filename']:
                self.project_id = i['project_id']
                break
        self.suspend = suspend
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0",55555))
        self.sock.listen(20)
        self.reads.append(self.sock)
        self.stop_threads = False
        self.thread = threading.Thread(target=self.recv_function)
        self.thread.start()
        self.process_thread = None
        self.connections = {}
        self.hosts = {}
        response = requests.get("http://%s/v2/projects/%s/nodes"%(GNS3_Main_Server, self.project_id))
        information = response.json()
        for i in (information):
            if (i['console_host'] == "0.0.0.0"):
                console_host = GNS3_Main_Server.split(":")[0]
            else:
                console_host = i['console_host']
            if ('Host' in i['name']):
                telnet_connect=Telnet(console_host, str(i['console']))
                telnet_connect.write("python3 /container_receiver.py".encode('ascii')+b"\r\n")
                self.hosts.setdefault(i['name'].split("-")[1],telnet_connect)

    def running_data(self, test_count, od_list, conn_id, delay, time_spend, exp_type):
        try:
            msg = "control-reset"
            for cid in self.connections:
                self.connections[cid].send(msg.encode())
            link = od_list.pop(0)
            link_id_txt = '%s,%s'%(link[0],link[1])
            link_id = self.links['%s,%s'%(link[0],link[1])]
            for od in od_list:
                sd_msg = "traffic-%d>142.%d.0.2>142.%d.0.2>%d"%(conn_id+10, int(od[0])+1, int(od[1])+1, time_spend)
                self.connections["142.%d.0.2"%(int(od[0])+1)].send(sd_msg.encode())
            time.sleep(3)
            msg = "control-reset"
            for cid in self.connections:
                    self.connections[cid].send(msg.encode())
            time.sleep(1+delay)
            if(self.suspend == True):
                payload = {
                    "suspend":True,
                }
                response = requests.put("http://%s/v2/projects/%s/links/%s"%(GNS3_Main_Server, self.project_id, link_id), json=payload)
                info = response.json()
                if exp_type == "Fibbing_Only":
                    time.sleep(50)
                elif exp_type == "Packet_Detection":
                    time.sleep(5)
                if (not(test_count % 10 == 0)):
                    msg = "control-recv"
                    for cid in self.connections:
                        self.connections[cid].send(msg.encode())
                time.sleep(2)
                payload = {
                    "suspend":False,
                }
                response = requests.put("http://%s/v2/projects/%s/links/%s"%(GNS3_Main_Server, self.project_id, link_id), json=payload)
                info = response.json()
                time.sleep(3)
            else:
                time.sleep(60)
        except(KeyboardInterrupt):
            print("Keyboard Interrupt. ")
            
    def recv_function(self):
        while (not(self.stop_threads)):
            try:
                os.chdir(os.getcwd()+'/result/')
                readable,writable,exception = select.select(self.reads, [], [])
                for r in readable:
                    if (r == self.sock):
                        client,addr = self.sock.accept()
                        self.reads.append(client)
                    else:
                        recv_message = r.recv(1514)
                        if not recv_message:
                            break
                        control,data = (recv_message.decode()).split("-")
                        if (control == "config"):
                            self.connections.setdefault(data,r)
                        elif (control == "exp"):
                            conn_id,src,dst,time = data.split(">")
                            conn_id = int(conn_id)-10
                            self.csv = open(self.filename, 'a')
                            src = int(src.split(".")[1])
                            dst = int(dst.split(".")[1])
                            self.csv.write("%d,%d,%d,%s\n"%(conn_id,src,dst,time))
                            self.csv.close()
            except(KeyboardInterrupt):
                print("Keyboard Interrupt. ")
                self.stop_threads = True
        
        for r in self.reads:
            r.close()
        for t in self.hosts:
            self.hosts[t].close()