import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.recoco import Timer
from pox.lib.revent.revent import EventMixin
from pox.lib.revent.revent import Event
from pox.lib.addresses import EthAddr
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.arp import arp
from pox.lib.packet.lldp import lldp
from pox.lib.util import dpidToStr
import networkx as nx
import numpy as np

class Port():
    def __init__(self, name, port_no, hw_addr):
        self.name = name
        self.port_no = port_no
        self.hw_addr = hw_addr

    def __str__(self):
        return f"\tPort:\n\t\tName: {self.name}\n\t\tPort No: {self.port_no}\n\t\tHW Addr: {self.hw_addr}"

class Link():
    def __init__(self, sid1, dpid1, port1, sid2, dpid2, port2):
        self.name = str(sid1) + "_" + str(sid2)
        self.sid1 = sid1
        self.dpid1 = dpid1
        self.port1 = int(port1)
        self.sid2 = sid2
        self.dpid2 = dpid2
        self.port2 = int(port2)

    def __eq__(self, other):
        if isinstance(other, Link):
            return self.name == other.name and self.sid1 == other.sid1 and self.dpid1 == other.dpid1 and self.port1 == other.port1 and self.sid2 == other.sid2 and self.dpid2 == other.dpid2 and self.port2 == other.port2
        return False

    def __str__(self):
        return f"\tLink:\n\t\tName: {self.name}\n\t\tSid1: {self.sid1}\n\t\tDpid1: {self.dpid1}\n\t\tPort1: {self.port1}\n\t\tSid2: {self.sid2}\n\t\tDpid2: {self.dpid2}\n\t\tPort2: {self.port2}"

class Switch():
    def __init__(self, dpid, name, ports=[]):
        self.dpid = dpid
        self.name = name
        self.ports = ports

    def __str__(self):
        ports_str = "\n".join([str(port) for port in self.ports])
        return f"Switch:\n\tDPID: {self.dpid}\n\tName: {self.name}\n\tPorts:\n{ports_str}"

class LinkDiscovery():
    def __init__(self):
        self.switches = {}
        self.links = {}
        core.openflow.addListeners(self)
        Timer(5, self.sendProbes, recurring=True)
        core.register('LinkDiscovery', self)

    def _handle_ConnectionUp(self, event):
        ports = []
        name = ""
        for port in event.ofp.ports:
            ports.append(Port(port.name, port.port_no, port.hw_addr))
            if "eth" not in port.name:
                name = port.name
        switch = Switch(event.dpid, name, ports)
        self.switches[switch.name] = switch
        self.install_flow_rule(switch.dpid)
        print("____________________________________switch_______________________________________")
        print("Connection Up: " + str(switch.dpid))
        print(switch)

    def _handle_PacketIn(self, event):
        if len(self.switches) < 5:
            return
        
        eth_frame = event.parsed
        if eth_frame.src == EthAddr("00:11:22:33:44:55"):
            eth_dst = eth_frame.dst
            switch1 = None
            switch2 = None
            port1 = None
            for i in self.switches:
                sw = self.switches[i]
                if sw.dpid == event.dpid:
                    switch2 = sw

            for i in self.switches:
                sw = self.switches[i]
                for j in range(len(sw.ports)):
                    if sw.ports[j].hw_addr == eth_dst:
                        switch1 = sw
                        port1 = sw.ports[j].port_no
            
            dpid1 = switch1.dpid
            dpid2 = event.dpid
            port2 = event.port
            link = Link(switch1.name, dpid1, port1, switch2.name, dpid2, port2)
            
            if (link.name not in self.links) and (link.dpid1 != link.dpid2):
                print("____________________________________link_______________________________________")
                self.links[link.name]=link
                print(link)

    def sendProbes(self):
        for switch_name in self.switches:
            switch = self.switches[switch_name]
            dpid = switch.dpid
            name = switch.name
            for port in switch.ports:
                if port.port_no != 65534:
                    mac_src = EthAddr("00:11:22:33:44:55")
                    mac_dst = port.hw_addr
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
        msg.priority = 500
        msg.cookie = 0x1
        match = of.ofp_match(dl_src = EthAddr("00:11:22:33:44:55"))
        msg.match = match
        msg.actions = [of.ofp_action_output(port = of.OFPP_CONTROLLER)]
        core.openflow.sendToDPID(dpid, msg)

    def getGraph(self, previousPath):
        N = len(self.switches)
        adj = np.zeros((N, N))
        max_weight = 0
        if previousPath is not None:
            tmp = []
            for i in range(len(previousPath)-1):
                tmp.append(str(previousPath[i]+1) + "_" + str(previousPath[i+1]+1))
                
            for link in self.links.keys():
                sw1 = int(self.links[link].sid1[1])-1
                sw2 = int(self.links[link].sid2[1])-1
                edge1 = str(sw1 + 1) + "_" + str(sw2 + 1)
                edge2 = str(sw2 + 1) + "_" + str(sw1 + 1)
                
                if (edge1 in tmp) or (edge2 in tmp): #se l'intero link è gia presente nel previous path allora il costo è circa nullo perchè nessun switch va riconfigurato
                    adj[sw1, sw2] = 0.1
                else:
                    if (sw1 in previousPath) or (sw2 in previousPath): #se solo uno tra gli switch è già presente nel previous path allora il costo è pari al numero di switch che vanno riconfigurati (c)
                        c = 0
                        pos = 0
                        for i in previousPath:
                            if sw1 == i or sw2 == i:
                                pos = c
                                break
                            c += 1
                        adj[sw1, sw2] = pos+2
                        if max_weight < pos+2:
                            max_weight = pos+2
                    else:    #se nessuno switch del nuovo path è presente nel previous path allora il costo è massimo
                        adj[sw1, sw2] = max_weight
        else:
            for link in self.links.keys():
                adj[int(self.links[link].sid1[1])-1, int(self.links[link].sid2[1])-1] = 0.1
                
        print(adj)
        print()
        graph = nx.from_numpy_array(adj)
        return graph

def launch():
    core.registerNew(LinkDiscovery)
