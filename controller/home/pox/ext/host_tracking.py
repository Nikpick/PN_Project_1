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
import time

class UserIsMoving(Event):
    def __init__ (self, packet, switch, interface):
        self.packet = packet
        self.switch = switch
        self.interface = interface

class HostTracking(EventMixin):
    
    _eventMixin_events = set([UserIsMoving])
    
    def __init__(self):
        self.position = None
        core.openflow.addListeners(self)
        
    def _handle_PacketIn(self, event):
        packet = event.parsed
        linksList = core.LinkDiscovery.links
        switches = core.LinkDiscovery.switches
        if packet.src != EthAddr("00:11:22:33:44:55"):
            dpid = event.connection.dpid

            current_switch = None
            for sw in switches:
                if switches[sw].dpid == dpid:
                    current_switch = switches[sw]
                    
            interface = event.port
            
            discovered = set()
            for link in core.LinkDiscovery.links:
                t = (core.LinkDiscovery.links[link].sid1, core.LinkDiscovery.links[link].port1)
                discovered.add(t)

            discovered.add(('s5', 2))
            tup = (current_switch.name, interface)
            if tup not in discovered:
                print(f"Mobile host is connected to {current_switch.name}, on the interface {interface-1}")
                if tup != self.position:
                    print("host has changed its position")
                    self.position = tup
                    self.raiseEvent(UserIsMoving(packet, current_switch, interface))

            pktOut = of.ofp_packet_out()

            if event.ofp.buffer_id is not None:
                pktOut.buffer_id = event.ofp.buffer_id
                pktOut.in_port = event.port
            else:
                pktOut.data = event.ofp
         
            action = of.ofp_action_output(port = of.OFPP_TABLE)
            pktOut.actions.append(action)
            event.connection.send(pktOut)


def launch ():
    core.registerNew(HostTracking)