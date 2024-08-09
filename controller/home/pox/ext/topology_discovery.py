import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.recoco import Timer
from pox.lib.addresses import EthAddr
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.arp import arp
from pox.lib.util import dpidToStr
import networkx as nx
import numpy as np

class Link():

	def __init__(self, switch1, switch2, dpid1, port1, dpid2, port2):
		self.name = str(switch1.name) + "_" + str(switch2.name)
		self.sid1 = switch1.sid
		self.sid2 = switch2.sid
		self.dpid1 = dpidToStr(dpid1)
		self.dpid2 = dpidToStr(dpid2)
		self.port1 = int(port1)
		self.port2 = int(port2)
	
	def __str__(self):
		return f"--->Link:\n------->Name: {self.name}\n------->Sid1: {self.sid1}\n------->Dpid1: {self.dpid1}\n------->Port1: {self.port1}\n------->Sid2: {self.sid2}\n------->Dpid2: {self.dpid2}\n------->Port2: {self.port2}"

class Switch():
	def __init__(self, dpid, name, sid, ports=[]):
		self.dpid = dpid
		self.name = name
		self.sid= sid
		self.ports = ports

	def port_to_string(self, port):
		return f"------->Port:\n----------->Name: {port.name}\n----------->Port No: {port.port_no}\n----------->HW Addr: {port.hw_addr}"

	def __str__(self):
		ports_str = "\n".join([self.port_to_string(port) for port in self.ports])
		return f"Switch:\n--->DPID: {self.dpid}\n--->Name: {self.name}\n--->Sid: {self.sid}\n--->Ports:\n{ports_str}"		

class linkDiscovery():

	def __init__(self):
		self.switches = {}
		self.links = {}
		self.switch_id = {}
		self.id = 1
		core.openflow.addListeners(self)
		Timer(5, self.sendProbes, recurring=True)

	def _handle_ConnectionUp(self, event):
		ports=[]
		name=""
		for port in event.ofp.ports:
			ports.append(port)
			if "eth" not in port.name:
				name = port.name
		switch = Switch(event.dpid, name, self.id, ports)
		self.switches[switch.name] = switch
		self.switch_id[self.id] = switch
		self.install_flow_rule(event.dpid)
		self.id += 1
		print("########################################################")
		print("New switch:")
		print(switch)

	def _handle_PacketIn(self, event):
		eth_frame = event.parsed
		if eth_frame.src == EthAddr("00:11:22:33:44:55"):
			eth_dst = eth_frame.dst.toStr().split(':')
			sid1 = int(eth_dst[4])
			switch1 = self.switch_id[sid1]
			dpid1 = switch1.dpid
			port1 = int(eth_dst[5])
			dpid2 = event.dpid
			port2 = event.ofp.in_port

			switch2 = next(switch for switch in self.switch_id.values() if switch.dpid == dpid2)

			link = Link(switch1, switch2, dpid1, port1, dpid2, port2)
			if link.name not in self.links:
				self.links[link.name] = link
				print("########################################################")
				print("Discovered new link:")
				print(link)

	def sendProbes(self):
		for switch_name in self.switches:
			switch = self.switches[switch_name]
			dpid = switch.dpid
			for port in switch.ports:
				if port.port_no != 65534:
					mac_src = EthAddr("00:11:22:33:44:55")
					mac_dst = EthAddr("00:00:00:00:" + str(switch.sid) + ":" + str(port.port_no))
					ether = ethernet()
					ether.type = ethernet.ARP_TYPE
					ether.src = mac_src
					ether.dst = mac_dst
					ether.payload = arp()
					msg = of.ofp_packet_out()
					msg.data = ether.pack()
					msg.actions.append(of.ofp_action_output(port = port.port_no))
					core.openflow.sendToDPID(dpid, msg)
				

	def install_flow_rule(self, dpid):
		msg = of.ofp_flow_mod()
		msg.priority = 50000
		match = of.ofp_match(dl_src = EthAddr("00:11:22:33:44:55"))
		msg.match = match
		msg.actions = [of.ofp_action_output(port = of.OFPP_CONTROLLER)]
		core.openflow.sendToDPID(dpid, msg)

	#returns a graph with weights depending on previous path
	def getGraph(self, previous_path=None):
		N = len(self.switches)
		adj = np.zeros((N, N))
		max_weight = 0
		if previous_path is not None:
			for link in self.links.values():
				sid1 = int(link.sid1)-1
				sid2 = int(link.sid2)-1
				link_in_previous_path = False
				for i in range(len(previous_path) - 1):
					if (previous_path[i] == sid1 and previous_path[i + 1] == sid2) or (previous_path[i] == sid2 and previous_path[i + 1] == sid1):
						link_in_previous_path = True
				
				if link_in_previous_path:
					adj[sid1, sid2] = 0.1 #minimum weight
				else:
					if (sid1 in previous_path) or (sid2 in previous_path): #add weight as much as all nodes to reconfigure
						nodes = 2 #at least 2 nodes
						if sid1 in previous_path:
							pos = previous_path.index(sid1)
						else:
							pos = previous_path.index(sid2)
						nodes += pos #amount of nodes to reconfigure depends on the position of one of the node in the previous path
						
						adj[sid1, sid2] = nodes
						
						if max_weight < nodes:
							max_weight = nodes
					else:
						adj[sid1, sid2] = max_weight
		else:
			for link in self.links.values():
				adj[int(link.sid1)-1, int(link.sid2)-1] = 0.1

		graph = nx.from_numpy_array(adj)
		print(graph)
		return graph

def launch():
	discovery = linkDiscovery()
	core.register("LinkDiscovery", discovery)