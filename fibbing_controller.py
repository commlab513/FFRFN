from time import sleep;
from configure_tool import Configurator
import packet_controller
import threading
import random
import socket
from scapy.all import *
import sys
import os
FILE_DIRECTION=os.getcwd()
load_contrib("ospf") 

# Environment values
delta = 0.02
windows = 3 # num of delta
timeBetweenExp = 10
waitSetupTime = 30

class Fake_Router:
	def __init__(self, topology, iface_R1, iface_R99):
        self.iface_R1 = iface_R1
        self.iface_R99 = iface_R99
		self.reads = []
		self.iface_sock_mapping = {}
		self.stop_threads = False
		self.fake_node = 20
		self.working_links = {}
		#for iface in ['enp7s0', 'enp3s0']:
        for iface in [iface_R1, iface_R99]:
			sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
			sock.bind((iface, 0))
			sock.setblocking(0)
			self.reads.append(sock)
			self.iface_sock_mapping.setdefault(iface, sock)
		self.seq = 0x80002000
		self.hidden_ip_address = {}
		self.pre_check_time = time.time()
		os.chdir(FILE_DIRECTION+"/projects/"+topology)
		hidden_ip_address = open("backup_ip_address.txt", "r")
		info = hidden_ip_address.read().split('\n')
		info.pop(-1)
		for i in info:
			data = i.split(" ")
			if data[0] not in self.hidden_ip_address:
				self.hidden_ip_address.setdefault(data[0], {})
			if data[1] not in self.hidden_ip_address:
				self.hidden_ip_address.setdefault(data[1], {})
			self.hidden_ip_address[data[0]].setdefault(data[1], data[3])
			self.hidden_ip_address[data[1]].setdefault(data[0], data[2])
		hidden_ip_address.close()
		self.link_disconnect = False
		self.threads = []
		self.threads.append(Thread(target=self.router))
		self.threads[-1].start()
		return
	
	def pack_OSPF_message(self, parsed, lsa_message):
		del (parsed[OSPF_LSUpd].lsalist)
		parsed[OSPF_LSUpd].lsalist=[lsa_message]
		parsed[OSPF_LSUpd].lsacount=1
		msg = Ether(src=parsed[Ether].src, dst=parsed[Ether].dst)/IP(src=parsed[IP].src,dst=parsed[IP].dst, ttl=1, tos=0xc0)/parsed[OSPF_Hdr]
		del(msg[IP].chksum)
		del(msg[OSPF_Hdr].chksum)
		del(msg[IP].len)
		del(msg[OSPF_Hdr].len)
		msg = (msg.__class__(bytes(msg)))
		self.seq += 1
		return msg

	def Type_5_LSA_Message(self, age, state_id, adrouter, forward_ip):
		lsa_header = []
		temp_link_info = OSPF_External_LSA(age=age, options=0x02, id=state_id, adrouter=adrouter, seq = self.seq, mask="255.255.255.255", metric=1, fwdaddr=forward_ip)
		del(temp_link_info.chksum)
		temp_link_info = (temp_link_info.__class__(bytes(temp_link_info)))
		lsa_header.append(temp_link_info)
		OSPF_LS_Update = OSPF_LSUpd(lsacount=1, lsalist=lsa_header)
		OSPF_Header = OSPF_Hdr(version=2,type=4,src="99.99.99.99")
		msg = Ether(src="aa:bb:cc:dd:ee:01", dst="01:00:5e:00:00:05")/IP(src="192.0.0.1",dst="224.0.0.5", ttl=1, tos=0xc0)/OSPF_Header/OSPF_LS_Update
		del(msg[IP].chksum)
		del(msg[OSPF_Hdr].chksum)
		msg = bytes(msg.__class__(bytes(msg)))
		self.iface_sock_mapping[self.iface_R1].send(msg)
		self.seq+=1
		return
	   
	def Fake_Node_Initial_Message(self, msg_type, age, parsed):
		if msg_type == 1: # Router LSA real node
			OSPF_Link_Message = []
			temp_link_info = OSPF_Link(id="99.99.99.99", data="255.255.255.255", type=3, toscount=0, metric=10)
			OSPF_Link_Message.append(temp_link_info)
			temp_link_info = OSPF_Link(id="192.0.0.1", data="192.0.0.2", type=2, toscount=0, metric=10)
			OSPF_Link_Message.append(temp_link_info)
			for i in range(self.fake_node):
				temp_link_info = OSPF_Link(id="192.0.%d.2"%(i+1), data="192.0.%d.1"%(i+1), type=2, toscount=0, metric=10)
				OSPF_Link_Message.append(temp_link_info)
			Router_LSA = OSPF_Router_LSA(age=0, options=2, type=1, id="99.99.99.99", adrouter="99.99.99.99", seq=self.seq, flags=0x2, linkcount=len(OSPF_Link_Message), linklist=OSPF_Link_Message)
			del(Router_LSA.chksum)
			Router_LSA = (Router_LSA.__class__(bytes(Router_LSA)))
			self.iface_sock_mapping[self.iface_R1].send(bytes(self.pack_OSPF_message(parsed, Router_LSA)))
			self.seq+=1
		elif msg_type == 2: # Router LSA for fake node
			for i in range(self.fake_node):
				router_id = i+101
				router_id_address = "%d.%d.%d.%d"%(router_id,router_id,router_id,router_id)
				OSPF_Link_Message = []
				temp_link_info = OSPF_Link(id=router_id_address, data="255.255.255.255", type=3, toscount=0, metric=10)
				OSPF_Link_Message.append(temp_link_info)
				temp_link_info = OSPF_Link(id="192.0.%d.2"%(i+1), data="192.0.%d.1"%(i+1), type=2, toscount=0, metric=10)
				OSPF_Link_Message.append(temp_link_info)
				Router_LSA = OSPF_Router_LSA(age=0, options=2, type=1, id=router_id_address, adrouter=router_id_address, seq=self.seq, flags=0x2, linkcount=len(OSPF_Link_Message), linklist=OSPF_Link_Message)
				del(Router_LSA.chksum)
				Router_LSA = (Router_LSA.__class__(bytes(Router_LSA)))
				self.iface_sock_mapping[self.iface_R1].send(bytes(self.pack_OSPF_message(parsed, Router_LSA)))
				self.seq+=1
		elif msg_type == 3:
			Network_LSA = OSPF_Network_LSA(age=0, options=2, type=2, id="192.0.0.1", adrouter="99.99.99.99", seq=self.seq, mask="255.255.255.0", routerlist=["99.99.99.99", "1.1.1.1"])
			del(Network_LSA.chksum)
			Network_LSA = (Network_LSA.__class__(bytes(Network_LSA)))
			self.iface_sock_mapping[self.iface_R1].send(bytes(self.pack_OSPF_message(parsed, Network_LSA)))
			self.seq += 1
			for i in range(self.fake_node):
				router_id = i+101
				router_id_address = "%d.%d.%d.%d"%(router_id,router_id,router_id,router_id)
				Network_LSA = OSPF_Network_LSA(age=0, options=2, type=2, id="192.0.%d.2"%(i+1), adrouter=router_id_address, seq=self.seq, mask="255.255.255.0", routerlist=["99.99.99.99", router_id_address])
				del(Network_LSA.chksum)
				Network_LSA = (Network_LSA.__class__(bytes(Network_LSA)))
				self.iface_sock_mapping[self.iface_R1].send(bytes(self.pack_OSPF_message(parsed, Network_LSA)))
				self.seq+=1
		return
	
	def Fake_Acknowledge_Message(self, parsed):
		OSPF_Header = OSPF_Hdr(version=2,type=5,src="1.1.1.1")
		lsa_header = []
		for i in range(parsed[OSPF_LSUpd].lsacount):
			temp_message = OSPF_LSA_Hdr(age=parsed[OSPF_LSUpd].lsalist[i].age, options=parsed[OSPF_LSUpd].lsalist[i].options, type=parsed[OSPF_LSUpd].lsalist[i].type, id=parsed[OSPF_LSUpd].lsalist[i].id, adrouter=parsed[OSPF_LSUpd].lsalist[i].adrouter, seq=parsed[OSPF_LSUpd].lsalist[i].seq, chksum=parsed[OSPF_LSUpd].lsalist[i].chksum)
			lsa_header.append(temp_message)
		OSPF_LS_Ack = OSPF_LSAck(lsaheaders = lsa_header) 
		msg = Ether(src="aa:bb:cc:dd:ee:02", dst="01:00:5e:00:00:05")/IP(src="192.0.0.2",dst="224.0.0.5",ttl=1,tos=0xc0)/OSPF_Header/OSPF_LS_Ack
		del(msg[IP].chksum)
		del(msg[OSPF_Hdr].chksum)
		msg = (msg.__class__(bytes(msg)))
		self.iface_sock_mapping[self.iface_R99].send(bytes(msg))
		return 
	
	def inject_lsa_cycle(self, od):
		for nodes in range(len(od)):
			state_id = "151.0.%d.%d"%(nodes%4,nodes+1)
			for n in range(len(od[nodes])-1):
				forward_ip = self.hidden_ip_address[od[nodes][n]][od[nodes][n+1]]
				adrouter = "%d.%d.%d.%d"%((101+int(od[nodes][n])),(101+int(od[nodes][n])),(101+int(od[nodes][n])),(101+int(od[nodes][n])))
				self.Type_5_LSA_Message(age=0, state_id=state_id, adrouter=adrouter, forward_ip=forward_ip)
		return 
	
	def inject_lsa_working(self, od):
		for idx in od:
			links = od[idx]
			for l in range(len(links)):
				forward_ip = self.hidden_ip_address[links[l][0]][links[l][1]]
				state_id = "142.%d.0.2"%(int(idx)+1)
				adrouter = "%d.%d.%d.%d"%((101+int(links[l][0])),(101+int(links[l][0])),(101+int(links[l][0])),(101+int(links[l][0])))
				self.Type_5_LSA_Message(age=0,state_id=state_id, adrouter=adrouter, forward_ip=forward_ip)
		return 

	def inject_lsa_backup(self, od, action):
		if action == 1:
			insert = "backup"
			delete = "working"
		elif action == 2:
			insert = "working"
			delete = "backup"
		
		for idx in od:
			links = od[idx]
			for l in range(len(links[insert])):
				forward_ip = self.hidden_ip_address[links[insert][l][0]][links[insert][l][1]]
				state_id = "142.%d.0.2"%(int(idx)+1)
				adrouter = "%d.%d.%d.%d"%((101+int(links[insert][l][0])),(101+int(links[insert][l][0])),(101+int(links[insert][l][0])),(101+int(links[insert][l][0])))
				age = 0
				self.Type_5_LSA_Message(age=0,state_id=state_id, adrouter=adrouter, forward_ip=forward_ip)
			for l in range(len(links[delete])):
				forward_ip = self.hidden_ip_address[links[delete][l][0]][links[delete][l][1]]
				state_id = "142.%d.0.2"%(int(idx)+1)
				adrouter = "%d.%d.%d.%d"%((101+int(links[delete][l][0])),(101+int(links[delete][l][0])),(101+int(links[delete][l][0])),(101+int(links[delete][l][0])))
				age = 3600
				self.Type_5_LSA_Message(age=3600,state_id=state_id, adrouter=adrouter, forward_ip=forward_ip)
		return

	def reset_link_disconnect(self):
		self.link_disconnect = False
		return
	
	def router(self):
		while (not(self.stop_threads)):
			try:
				readable, writable, exceptional = select(self.reads, [], [])
				for r in readable:
					msg = r.recv(1514)
					parsed = Ether(msg)
                    if self.iface_sock_mapping[self.iface_R1] == r:
						if parsed.haslayer(OSPF_Hdr) and parsed[OSPF_Hdr].type == 5:
							continue
						elif parsed.haslayer(OSPF_Hdr) and parsed[OSPF_Hdr].type == 4:
							if parsed.haslayer(OSPF_LSUpd):
								for lsa_info in parsed[OSPF_LSUpd].lsalist:
									if lsa_info.type == 2 and lsa_info.age == 3600:
										self.link_disconnect = True
						self.iface_sock_mapping[self.iface_R99].send(msg)
					elif self.iface_sock_mapping[self.iface_R99] == r:
						if parsed.haslayer(OSPF_Hdr) and parsed[OSPF_Hdr].type == 4:
							self.Fake_Acknowledge_Message(parsed = parsed)
							for i in range(3):
								self.Fake_Node_Initial_Message(msg_type=i+1, age=0, parsed = parsed)
						else:
							self.iface_sock_mapping[self.iface_R1].send(msg)
                    
			except(KeyboardInterrupt):
				self.stop_threads = True
	
	def read_link_disconnect(self):
		return self.link_disconnect
	
	def reset_link_disconnect(self):
		self.link_disconnect = False
		return 

	def stop_system_threads(self):
		self.stop_threads = True

class Cycle_Controller:
	def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver
		self.reads = []
		self.cycles = []
        
        # Interfaces configurations
		self.ifaces = {
			sender:{
				"sock":None, 
				'mac':'84:16:f9:06:ed:9f', 
				"arp_template":[],
				'cycle_info':[
					{'gw_ip':'141.0.0.254', "gw_mac": "1a:2b:3c:4d:51:61"},
					{'gw_ip':'141.0.1.254', "gw_mac": "1a:2b:3c:4d:51:62"},
					{'gw_ip':'141.0.2.254', "gw_mac": "1a:2b:3c:4d:51:63"},
					{'gw_ip':'141.0.3.254', "gw_mac": "1a:2b:3c:4d:51:64"},
				]
			},
			receiver:{
				"sock":None, 
				'mac':'c0:4a:00:01:88:51', 
				"arp_template":[],
				'cycle_info':[
					{'gw_ip':'151.0.0.254', "gw_mac": "1a:2b:3c:4d:52:61"},
					{'gw_ip':'151.0.1.254', "gw_mac": "1a:2b:3c:4d:52:62"},
					{'gw_ip':'151.0.2.254', "gw_mac": "1a:2b:3c:4d:52:63"},
					{'gw_ip':'151.0.3.254', "gw_mac": "1a:2b:3c:4d:52:64"},
				]
			}
		}
		for iface in self.ifaces:
			sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
			sock.bind((iface, 0))
			sock.setblocking(0)
			self.ifaces[iface]['sock'] = sock
			if iface == self.receiver:
				self.reads.append(sock)
		
        # Generating monitoring cycle messages
        self.cycle_message = []
		for i in self.ifaces:
			for c in range(50):
				subnet=c%4
				j = self.ifaces[i]['cycle_info'][subnet]
				gw_ip = j['gw_ip']
				ip_split = j['gw_ip'].split(".")
				host_ip = "%s.%s.%d.%d"%(ip_split[0],ip_split[1],subnet, c+1)
				self.ifaces[i]["arp_template"].append(bytes(Ether(dst = "ff:ff:ff:ff:ff:ff", src=self.ifaces[i]['mac'])/ARP(op=1,psrc="%s"%(host_ip), pdst="%s"%(gw_ip), hwsrc=self.ifaces[i]['mac'], hwdst="00:00:00:00:00:00")))
		self.threads = []
		self.threads.append(threading.Thread(target=self.recv_function))
		self.stop_threads = False
		for t in self.threads:
			t.start()
		self.arp()
		time.sleep(5)

		iface = self.sender
		for c in range(50):
			subnet = c%4
			j = self.ifaces[iface]['cycle_info'][subnet]
			ip_split = j['gw_ip'].split(".")
			src_host_ip = "141.0.%d.%d"%(subnet, c+1)
			dst_host_ip = "151.0.%d.%d"%(subnet, c+1)
			msg = Ether(dst = j['gw_mac'], src = self.ifaces[iface]['mac'])/IP(src=src_host_ip,dst=dst_host_ip, tos=0xc0)/UDP(sport=7777,dport=8888)/Raw(load=bytes(64-42))
			del(msg[IP].chksum)
			del(msg[UDP].chksum)
			self.cycle_message.append(bytes(msg.__class__(bytes(msg))))
		
		self.cycles = [0.0] * (50)


	def send_cycle(self, num_cycle_packet):
		iface = self.sender
		sock = self.ifaces[iface]['sock']
		for c in range(num_cycle_packet):
			sock.send(self.cycle_message[c])
	
	def arp (self):
		for iface in self.ifaces:
			for arp_msg in self.ifaces[iface]["arp_template"]:
				self.ifaces[iface]['sock'].send(arp_msg)
	
	def recv_function(self):
		while (not(self.stop_threads)):
			try:
				readable,writable, exceptional = select(self.reads, [], [])
				for r in readable:
					msg = r.recv(64)
					parsed = Ether(msg)
					if parsed.haslayer(IP) and parsed.haslayer(UDP):
						src = (parsed[IP].src).split(".")
						if src[0] == "141" and src[1] == "0":
							self.cycles[int(src[3])-1] += 1
			except(KeyboardInterrupt):
				self.stop_system_threads()
	
	def return_result(self, num_cycle_packet):
		cycles = self.cycles[0:num_cycle_packet]
		self.cycles = [0] * 50
		return cycles
	
	def stop_system_threads(self):
		self.stop_threads = True
		return 

class fibbing_controller:
	def __init__(self, exp_type, topology, seed, test_count, sender, receiver, iface_R1, iface_R99):
		self.stop_thread = False
		self.topology = topology
		self.seed = int(seed)
		self.test_count = int(test_count)
		self.exp_type = exp_type
		self.detect_failure_flag = 0
		self.run_init_time = 0.0
		self.detect_time = 1
		self.detect_flag_success_time = -1
		self.success = 0
		self.failure = 0
        self.cycle_sender = sender
        self.cycle_receiver = receiver
        self.fake_router_iface_R1=iface_R1
        self.fake_router_iface_R99=iface_R99
		return
	
    # Checking monitoring cycle patterns
	def check_pattens(self, pattens_list, recvCyclePatten, cycle_count):
		sumRecvCyclePatten = [sum(x) for x in zip(*recvCyclePatten)]
		print (sumRecvCyclePatten)
		if (self.detect_failure_flag == 0):
			for i in range(cycle_count):
				if (sumRecvCyclePatten[i] == 0):
					self.detect_failure_flag = 1
					break
		else:
			self.detect_failure_flag += 1
		
		if (self.detect_failure_flag > self.detect_time):
			patten = [False]*cycle_count
			for i in range(cycle_count):
				if (sumRecvCyclePatten[i] != 0) :
					patten[i] = True
			for p in range(len(pattens_list)):
				if pattens_list[p] == patten:
					self.detect_flag_success_time = (time.time()-self.run_init_time)
					self.success += 1
					return p
			print("Debug: patten_list cannot return p")
			self.failure += 1
			return cycle_count
		return -1

	def main(self):
		topo = self.topology
		
		# read Fibbing Experiment File
		os.chdir(FILE_DIRECTION+'/experiment/Fibbing')
		file = open("exp_Fibbing_%s.txt"%topo, 'r')
		exp = file.read().split('\n')
		exp.pop(0) # skip nubmer of link
		exp.pop(-1)
		exp_list = []
		for e in exp:
			tmp = e.split(" ")
			tmp.pop(-1)
			od_list = []
			for i in tmp:
				src,dst = i.split(",")
				od_list.append([src,dst])
			exp_list.append(od_list)
		# end read Fibbing Experiment File
		
		# read Cycle File
		os.chdir(FILE_DIRECTION+'/cycle/')
		file = open("cycle_%s.txt" % topo, 'r')
		cycle = file.read().split('\n')
		cycle_count = int(cycle.pop(0)) # skip number of cycle
		cycle.pop(-1)
		
		cycle_list = []
		for c in cycle:
			tmp = c.split(" ")
			tmp.pop(-1)
			cycle_list.append(tmp)
		# end read Cycle File
		
		# read Pattens File
		os.chdir(FILE_DIRECTION+'/pattens/')
		file = open("pattens_%s.txt" % topo, 'r')
		pattens = file.read().split('\n')
		pattens.pop(0) # skip nubmer of link
		pattens.pop(0) # skip number of cycle
		pattens.pop(-1)
		
		pattens_list = []
		for p in pattens:
			tmp = p.split(" ")
			tmp.pop(-1)
			#print (tmp)
			bool_tmp = []
			for t in tmp:
				if t == '1':
					bool_tmp.append(False)
				elif t == '0':
					bool_tmp.append(True)
			pattens_list.append(bool_tmp)
		#print(pattens_list)
		# end Pattens File

		# read Working File
		os.chdir(FILE_DIRECTION+'/FibbingRouting/Working/')
		file = open("fibbing_working_%s.txt" % topo, 'r')
		working = file.read().split('\n')
		total_node_count = int(working.pop(0)) # nubmer of node
		working.pop(-1)

		working_list = {}
		for i in range(int(total_node_count)):
			n_id = working.pop(0)
			wk = working.pop(0)
			tmp = wk.split(" ")
			tmp.pop(-1)
			link_list = []
			for l in tmp:
				src,dst = l.split(",")
				link_list.append([src,dst])
			working_list.setdefault(n_id,link_list)
		#print(working_list)
		# end read Working File
		
		# read Backup File
		os.chdir(FILE_DIRECTION+'/FibbingRouting/Backup/')
		file = open("fibbing_backup_%s.txt" % topo, 'r')
		backup = file.read().split('\n')
		total_link_count = int(backup.pop(0)) # nubmer of link
		backup.pop(-1)
			
		backup_list = []
		for i in range(int(total_link_count)):
			l_id = backup.pop(0).split(" ")
			effect_od_count = l_id.pop(-1)
			od_list = {}
			for j in range(int(effect_od_count)):
				od = backup.pop(0) # Tree destination
				w = backup.pop(0)	# working 
				tmp = w.split(" ")
				tmp.pop(-1)
				w_link_list = []
				for l in tmp:
					src,dst = l.split(",")
					w_link_list.append([src,dst])
				b = backup.pop(0)
				tmp = b.split(" ")
				tmp.pop(-1)
				b_link_list = []
				for l in tmp:
					src,dst = l.split(",")
					b_link_list.append([src,dst])
				od_list[od] = {'working':w_link_list, 'backup':b_link_list}
			backup_list.append(od_list)
		# end read Backup File

		# Configure GNS3 Testbed
		config = Configurator(topo)
		config.get_topology_info()
		config.start_topology()
		sleep(waitSetupTime)
		
		# Configure Fake Router
		fake_router = Fake_Router(topo, self.fake_router_iface_R1, self.fake_router_iface_R99)
		sleep(waitSetupTime)
		
		# Configure TestBed
		pc = packet_controller.Packet_Controller(topology=topo, suspend=True)
		if self.exp_type == 'Packet_Detection':
			cycle_controller = Cycle_Controller(self.cycle_sender, self.cycle_receiver)
			time_spend = 15
		else:
			time_spend = 60
		random.seed(self.seed)
		for test_count in range(self.test_count+2):
			link_id = random.randint(0,total_link_count-1)
			link_info = exp_list[link_id][0]
			exp_working = random.choices(exp_list[link_id][1:], k=1)[0]
			test_data = [link_info,exp_working]
			if (test_count%10==0):
				# setup Cycle Paths
				fake_router.inject_lsa_cycle(cycle_list)
				# setup Working Paths
				fake_router.inject_lsa_working(working_list)
				sleep(5)
			detected_failure = -1
			self.detect_failure_flag = 0
			r = random.random()
			PacketControllerThread = threading.Thread(target = pc.running_data, args = (test_count, test_data,link_id,r,time_spend, self.exp_type,))
			PacketControllerThread.start()
			self.run_init_time = time.time()+r+2
			self.stop_thread = False
			if  self.exp_type == 'Fibbing_Only':
				dis = fake_router.read_link_disconnect() # recv OSPF link disconnection (LS age = 3600)
				# wait for detection
				while(not(dis)):
					dis = fake_router.read_link_disconnect()
			elif self.exp_type == 'Packet_Detection':
				init_time = time.time()
				recvCyclePatten = [[1]*cycle_count]*windows
				while detected_failure < 0:
					cc_thread = threading.Thread(target=cycle_controller.send_cycle, args=(cycle_count,))
					cc_thread.start()
					recvCyclePatten.append(cycle_controller.return_result(cycle_count))
					recvCyclePatten.pop(0)
					if (time.time() - init_time) > 1:
						detected_failure = self.check_pattens(pattens_list, recvCyclePatten, cycle_count)
					
					if detected_failure < 0:
						sleep(delta)
					

			self.stop_thread = True
			fake_router.inject_lsa_backup(backup_list[link_id], 1)
			PacketControllerThread.join()
			fake_router.inject_lsa_backup(backup_list[link_id], 2)
			if  self.exp_type == 'Fibbing_Only':
				fake_router.reset_link_disconnect() # reset disconnect flag
			if not((test_count%10==0)):
				print ("Topo: %s, exp count: %d/%d, link id(d/r): %d/%d, working path: %s, detection time: %s,done"%(topo,test_count+1,self.test_count,detected_failure,link_id,exp_working,str(self.detect_flag_success_time)))
			self.detect_flag_success_time = -1
		print("Success: %d, Failure: %d"%(self.success, self.failure))
		config.stop_topology()
		os.system("sudo kill -9 $(ps -aux | grep ./fibbing_controller.py | awk '{print $2}' | xargs ) > /dev/null 2>&1")
		
if __name__ == '__main__':
	fb = fibbing_controller(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8])
	fb.main()
