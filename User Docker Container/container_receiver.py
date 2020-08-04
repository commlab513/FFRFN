import socket 
import threading
import os
import netifaces
from scapy.all import *

class Container:
    def __init__(self):
        self.stop_threads = False
        self.result = {}
        self.threads = []
        self.recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
        self.recv_sock.bind(("eth0",0))
        self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.iface_ip = netifaces.ifaddresses('eth0')[netifaces.AF_INET][0]['addr']
        while (True):
            try:
                self.control_sock.connect(("172.16.20.111",55555))
                break
            except:
                pass
        msg = "config-%s"%self.iface_ip
        self.control_sock.send(msg.encode())
        self.threads.append(threading.Thread(target=self.recv_function))
        self.threads[-1].start()
    
    def recv_function(self):
        while (not(self.stop_threads)):
            try:
                msg = self.recv_sock.recv(64)
                if not msg:
                    break
                curr_time = time.time()
                if not(msg[42:44] == b"\xff\xff"):
                    parsed = Ether(msg)
                    if parsed.haslayer(IP) and parsed.haslayer(UDP):
                        if parsed[IP].dst == self.iface_ip:
                            conn_id = parsed[UDP].dport-7000
                            pair = "%d_%s_%s"%(conn_id,parsed[IP].src,parsed[IP].dst)
                            if (pair not in self.result):
                                self.result.setdefault(pair, {"max_time":0.0, "pre_time":curr_time})
                            else:
                                if (curr_time-self.result[pair]["pre_time"] > self.result[pair]["max_time"]):
                                    self.result[pair]["max_time"] = curr_time-self.result[pair]["pre_time"]
                            self.result[pair]["pre_time"] = curr_time
            except(KeyboardInterrupt):
                self.stop_threads = True
                break
            

    def main(self):
        while (not(self.stop_threads)):
            try:
                control_msg = self.control_sock.recv(1514)
                if not control_msg:
                    break
                control_msg = control_msg.decode()
                print (control_msg)
                select,data=control_msg.split("-")
                if(select == "control"):
                    if (data == "reset"):
                        self.result = {}
                    elif (data == "recv"):
                        for r in self.result:
                            print (r)
                            conn_id,src,dst = r.split("_")
                            self.control_sock.send(("exp-%s>%s>%s>%s"%(conn_id,src,dst,str(self.result[r]["max_time"]))).encode())
                elif (select == "traffic"):
                    conn_id,src,dst,time_spend = data.split(">")
                    os.system("iperf -c %s -u -b 50k -l 22 -t %d -p %d & "%(dst,(int(time_spend)),(int(conn_id)+7000)))
            except(KeyboardInterrupt):
                self.stop_threads = True
                for t in self.threads:
                    t.join()
                break 
        self.recv_sock.close()
        self.control_sock.close()
            

if "__main__" in __name__:
    container = Container()
    container.main()
        
