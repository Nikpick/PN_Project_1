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

class FakeGateway (EventMixin):

    def __init__ (self):
        core.openflow.addListeners(self)
        
    def _handle_ConnectionUp(self, event):
        pass
                       
    def _handle_PacketIn(self, event):
        switches = core.LinkDiscovery.switches
        packet = event.parsed

        arp_packet = packet.find('arp')
        if arp_packet is None:
            return

        if arp_packet.opcode == arp.REQUEST: 
            arp_reply = arp()
            if switches["s5"].ports[1].name != "s5":
                arp_reply.hwsrc = switches["s5"].ports[1].hw_addr
            else:
                arp_reply.hwsrc = switches["s5"].ports[0].hw_addr
            arp_reply.hwdst = arp_packet.hwsrc
            arp_reply.opcode = arp.REPLY 
            arp_reply.protosrc = arp_packet.protodst 
            arp_reply.protodst = arp_packet.protosrc
            
            ether = ethernet() 
            ether.type = ethernet.ARP_TYPE 
            ether.dst = arp_packet.hwsrc 
            if switches["s5"].ports[1].name != "s5":
                ether.src = switches["s5"].ports[1].hw_addr
            else:
                ether.src = switches["s5"].ports[0].hw_addr
            ether.payload = arp_reply
            
            msg = of.ofp_packet_out() 
            msg.data = ether.pack() 
            msg.in_port = event.port
            msg.actions.append(of.ofp_action_output(port = of.OFPP_IN_PORT))  
            
            connection = event.connection
            event.connection.send(msg)
            
        return

def launch ():
    core.registerNew(FakeGateway)