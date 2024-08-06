import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.arp import arp
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.util import dpidToStr
import networkx as nx

class User_mobility():

	def __init__(self):
		core.openflow.addListeners(self)
		core.HostTracking.addListeners(self)
		self.previousPath = None
	
	def dijkstra(self, graph, source, destination):
		best_path = nx.dijkstra_path(graph, source=source, target=destination, weight='weight')
		return best_path

	def _handle_UserIsMoving(self, event):
		print("___________________handle_UserIsMoving_____________________________________")
		
		graph = core.LinkDiscovery.getGraph(self.previousPath)

		S = int(event.switch.name[1])-1
		D = int(core.LinkDiscovery.switches["s5"].name[1])-1
		path = self.dijkstra(graph, S, D)
			
		printable_path = ""
		for n in path:
			printable_path = printable_path + str(n+1) + " --> "
			
		print(printable_path)

		add_rules = []
		remove_rules = []

		for s in range(len(path) - 1):
			add_rules.append(f"s{path[s]+1}_s{path[s+1]+1}")
		
		if self.previousPath is not None:
			for s in range(len(self.previousPath) - 1):
				l = f"s{self.previousPath[s]+1}_s{self.previousPath[s+1]+1}"
				remove_rules.append(l)

		mac_internet = "00:00:00:00:66:00"
		mac_mh = event.packet.src
		mac_gw_external = ""
		mac_gw_internal = ""
		for port in core.LinkDiscovery.switches["s5"].ports:
			if port.port_no == 2:
				mac_gw_external = port.hw_addr
			elif port.port_no == 1: 
				mac_gw_internal = port.hw_addr
		
		self.previousPath = path
		self.update_flow_rules(event.packet, add_rules, remove_rules, event.interface, mac_mh, mac_internet, mac_gw_external, mac_gw_internal)

			
	def update_flow_rules(self, packet, add_rules, remove_rules, initial_interface, mac_mh, mac_internet, mac_gw_external, mac_gw_internal):
		switches = core.LinkDiscovery.switches
		
		#rimuovi tutte le flow rules non utilizzate
		for rule in remove_rules:
			dpid1 = core.LinkDiscovery.switches[rule.split('_')[0]].dpid
			dpid2 = core.LinkDiscovery.switches[rule.split('_')[1]].dpid
			msg = of.ofp_flow_mod()
			msg.command = of.OFPFC_DELETE
			msg.out_port = of.OFPP_NONE
			msg.match = of.ofp_match()
			if dpid1 != core.LinkDiscovery.switches["s5"].dpid:
				core.openflow.sendToDPID(dpid1, msg)
			if dpid2 != core.LinkDiscovery.switches["s5"].dpid:
				core.openflow.sendToDPID(dpid2, msg)

		#installa le flow rules per comunicare con il controller
		for i in core.LinkDiscovery.switches:
			msg = of.ofp_flow_mod()
			msg.priority = 500
			msg.cookie = 0x2
			match = of.ofp_match(dl_src = EthAddr("00:11:22:33:44:55"))
			msg.match = match
			msg.actions = [of.ofp_action_output(port = of.OFPP_CONTROLLER)]
			core.openflow.sendToDPID(core.LinkDiscovery.switches[i].dpid, msg)

		#se un pacchetto è diretto verso internet
		GWdpid = switches["s5"].dpid
		msg1 = of.ofp_flow_mod()
		msg1.priority = 500
		msg1.match = of.ofp_match(in_port=1)
		# Crea un'azione per modificare l'indirizzo MAC di destinazione
		action_change_dst_mac = of.ofp_action_dl_addr()
		action_change_dst_mac.type = of.OFPAT_SET_DL_DST
		action_change_dst_mac.dl_addr = EthAddr(mac_internet)
		msg1.actions.append(action_change_dst_mac)
		# Crea un'azione per modificare l'indirizzo MAC sorgente
		action_change_src_mac = of.ofp_action_dl_addr()
		action_change_src_mac.type = of.OFPAT_SET_DL_SRC
		action_change_src_mac.dl_addr = EthAddr(mac_gw_external)
		msg1.actions.append(action_change_src_mac)
		# Aggiungi l'azione di output alla fine
		msg1.actions.append(of.ofp_action_output(port=2))
		core.openflow.sendToDPID(GWdpid, msg1)
		
		#se un pacchetto è diretto verso il mobile host
		msg2 = of.ofp_flow_mod()
		msg2.priority = 500
		msg2.match = of.ofp_match(in_port=2)
		# Crea un'azione per modificare l'indirizzo MAC di destinazione
		action_change_dst_mac = of.ofp_action_dl_addr()
		action_change_dst_mac.type = of.OFPAT_SET_DL_DST
		action_change_dst_mac.dl_addr = EthAddr(mac_mh)
		msg2.actions.append(action_change_dst_mac)
		# Crea un'azione per modificare l'indirizzo MAC sorgente
		action_change_src_mac = of.ofp_action_dl_addr()
		action_change_src_mac.type = of.OFPAT_SET_DL_SRC
		action_change_src_mac.dl_addr = EthAddr(mac_gw_internal)
		msg2.actions.append(action_change_src_mac)
		
		msg2.actions.append(of.ofp_action_output(port=1))
		core.openflow.sendToDPID(GWdpid, msg2)
		
		for i in range(len(add_rules)):
			prev_rule = ""
			prev_link = None
			if i > 0:
				prev_rule = add_rules[i-1]
				prev_link = core.LinkDiscovery.links[prev_rule]
			rule = add_rules[i]
			link = core.LinkDiscovery.links[rule]
			
			switch_name = link.name.split("_")[0]
			
			msg = of.ofp_flow_mod()
			msg.priority = 500

			downlink_msg = of.ofp_flow_mod()
			downlink_msg.priority = 500

			if prev_link is not None:
				msg.match = of.ofp_match(in_port=prev_link.port2)
				downlink_msg.match = of.ofp_match(in_port=link.port1)
				downlink_msg.actions = [of.ofp_action_output(port=prev_link.port2)]
			else:
				msg.match = of.ofp_match(in_port=initial_interface)
				downlink_msg.match = of.ofp_match(in_port=link.port1)
				downlink_msg.actions = [of.ofp_action_output(port=initial_interface)]

			msg.actions = [of.ofp_action_output(port=link.port1)]			
			dpid = switches[switch_name].dpid
			
			core.openflow.sendToDPID(dpid, msg)
			core.openflow.sendToDPID(dpid, downlink_msg)

def launch():
	core.registerNew(User_mobility)