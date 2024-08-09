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

            #exept for s2, if not a link, then connection from outside
            not_a_link = current_switch.name != "s2" or all((link.sid1 != current_switch.name and link.port1 != current_interface) for link in links)
            current_connection = (current_switch.name, current_interface)
            if  not_a_link:
                if (current_connection != self.last_connection):
                    print(f"A mobile connected to {current_switch.name}, on the interface {current_interface}")
                    self.last_connection = current_connection
                    self.raiseEvent(PositionChanged(packet, current_switch, current_interface, event.connection))


def launch ():
    core.registerNew(HostTracking)