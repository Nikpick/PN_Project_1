import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.addresses import EthAddr
import networkx as nx

class User_mobility():

	def __init__(self):
		core.openflow.addListeners(self)
		core.HostTracking.addListeners(self)
		self.previous_path = None
		self.addedd = False

	def _handle_PositionChanged(self, event):
	
		switches = core.LinkDiscovery.switches
		switch_id = core.LinkDiscovery.switch_id
		links = core.LinkDiscovery.links
		switch_src = event.switch
		switch_dst = switches["s2"] #s2 is always the destination since is connected to the gw
		S = int(switch_src.sid)-1
		D = int(switch_dst.sid)-1
		graph = core.LinkDiscovery.getGraph(self.previous_path)
		path = nx.dijkstra_path(graph, source=S, target=D, weight='weight')

		path_str = ""
		for p in path:
			if path.index(p) == len(path)-1:
				path_str +=  switch_id[p+1].name
			else:
				path_str += switch_id[p+1].name + "-"

		print(f"**INFO**: The path used in the connection is:\n")

		parts = path_str.split('-')
		connection_str = '======'.join(parts)
		border = '-' * (len(connection_str) + 4)

		# Print the formatted output
		print(border)
		print(f"| {connection_str} |")
		print(border + "\n")

		

		#if there was a previous path before, at the first we remove the rule to the mobile and all rules that are not in the new path
		if self.previous_path is not None:
			old_first_switch = switch_id[self.previous_path[0]+1]
			print("**INFO**: I'm " + old_first_switch.name +" and I'm the first of the previous path")
			self.del_flow_rule(old_first_switch.dpid, True)

			for p in self.previous_path:
				if p not in path:
					print("**INFO**: I'm " + switch_id[p+1].name + " and I'm not in the new path")
					self.del_flow_rule(switch_id[p+1].dpid, True)
					self.del_flow_rule(switch_id[p+1].dpid, False)

			print("**INFO**: All the previous rules were deleted\n")


		# Retrieve switches from the dictionary
		switches_in_path = [switch_id[sid+1] for sid in path]
		# Install the flow rules for the outward journey
		for i in range(len(switches_in_path) - 1):
			
			pre_switch = switches_in_path[i]
			post_switch = switches_in_path[i+1]

			# Find the link name and output ports
			link_name = f"{pre_switch.name}_{post_switch.name}"
			link = links[link_name]
			out_port1 = link.port1
			out_port2 = link.port2

			
			#print("**INFO**: I am link:  " + str(link_name) +" "+  str(link.port1) +" "+str(link.port2))

			if i == 0: #add to the first the address to the cabinet
				print("**INFO**: This is the first link:")
				self.add_flow_rule(pre_switch.dpid, event.interface, True)
			if i == len(switches_in_path)-2 and not self.addedd: #add addressing to GW at last
				print("**INFO**: This is the last link:")
				for port in post_switch.ports:
					if port.name == "eth3":
						outport = port.port_no
				self.add_flow_rule(post_switch.dpid, outport, False)
				self.addedd = True
			print(link)

			if self.previous_path is not None:
				
				# Check whether pre_switch and post_switch are adjacent in the previous_path list
				if (pre_switch.sid-1 in self.previous_path) and (post_switch.sid-1 in self.previous_path):
					print("**INFO**: Bot in previous path")
					pre_index = self.previous_path.index(pre_switch.sid-1)
					post_index = self.previous_path.index(post_switch.sid-1)
					if post_index - pre_index == 1:
						continue  # Skip loop iteration if pre_switch and post_switch are adjacent 
				
				#check whether one of them was in the previous path
				if (pre_switch.sid-1 in self.previous_path) or (post_switch.sid-1 in self.previous_path):
					if (pre_switch.sid-1 in self.previous_path):
						self.mod_flow_rule(pre_switch.dpid, out_port1 ,False) #if it is the first, change to gw
						self.add_flow_rule(post_switch.dpid, out_port2 ,True)
						print("**INFO**: Only pre switch in previous path")
						continue
					else:
						self.mod_flow_rule(post_switch.dpid, out_port2 ,True) #if it is the second change to mobile
						self.add_flow_rule(pre_switch.dpid, out_port1 ,False)
						print("**INFO**: Only post switch in previous path")
						continue
			
			print("**INFO**: Adding all the missing rules\n")
			#if not add the return rules
			self.add_flow_rule(pre_switch.dpid, out_port1 ,False)
			self.add_flow_rule(post_switch.dpid, out_port2 ,True)

		
		self.previous_path = path

	def add_flow_rule(self, dpid, out_port, mobile):
		msg = of.ofp_flow_mod()
		msg.priority=500
		
		if mobile:
			msg.match.dl_src = EthAddr("00:00:00:00:00:01")
		else:
			msg.match.dl_dst = EthAddr("00:00:00:00:00:01")

		msg.actions.append(of.ofp_action_output(port=out_port))
		core.openflow.sendToDPID(dpid, msg)

	def mod_flow_rule(self, dpid, out_port, mobile):
		msg = of.ofp_flow_mod()
		msg.command = of.OFPFC_MODIFY
		msg.priority=500
		
		if mobile:
			msg.match.dl_src = EthAddr("00:00:00:00:00:01")
		else:
			msg.match.dl_dst = EthAddr("00:00:00:00:00:01")

		msg.actions.append(of.ofp_action_output(port=out_port))
		core.openflow.sendToDPID(dpid, msg)

	def del_flow_rule(self, dpid, mobile):
		msg = of.ofp_flow_mod()
		msg.command = of.OFPFC_DELETE
		msg.priority=500
		if mobile:
			msg.match.dl_src = EthAddr("00:00:00:00:00:01")
		else:
			msg.match.dl_dst = EthAddr("00:00:00:00:00:01")
		core.openflow.sendToDPID(dpid, msg)


def launch():
	core.registerNew(User_mobility)
