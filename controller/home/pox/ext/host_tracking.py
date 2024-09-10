from pox.core import core
from pox.lib.revent.revent import EventMixin
from pox.lib.revent.revent import Event
from pox.lib.addresses import EthAddr

class PositionChanged(Event):
    def __init__ (self, packet, switch, interface, connection):
        self.packet = packet
        self.switch = switch
        self.interface = interface
        self.connection = connection

class HostTracking(EventMixin):
    
    _eventMixin_events = set([PositionChanged])
    
    def __init__(self):
        self.last_ip_connection = None
        self.last_connection = None
        core.openflow.addListeners(self)
        
    def _handle_PacketIn(self, event):
        packet = event.parsed
        
        switches = core.LinkDiscovery.switches.values()
        links = core.LinkDiscovery.links.values()

        if packet.src != EthAddr("00:11:22:33:44:55"):
            dpid = event.connection.dpid  
            current_switch = next(switch for switch in switches if switch.dpid == dpid)
            current_interface = event.port

            #first I find all the links where the current switch is in the first position
            possible_links = [link for link in links if link.sid1 == current_switch.sid]
            for link in possible_links:
                print(link.name)

            #excluding s2 (since it only handles GW packets), if the interface the packet is coming from is not part of the possible links, then is a new connection from a mobile
            not_a_link = current_switch.name != "s2" and all((link.port1 != current_interface) for link in possible_links)
            print(not_a_link)
            current_connection = (current_switch.name, current_interface)
            if  not_a_link:
                if (current_connection != self.last_connection):
                    print(f"A mobile connected to {current_switch.name}, on the interface {current_interface}")
                    self.last_connection = current_connection
                    self.raiseEvent(PositionChanged(packet, current_switch, current_interface, event.connection))


def launch ():
    core.registerNew(HostTracking)