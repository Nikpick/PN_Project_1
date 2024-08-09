import pox.openflow.libopenflow_01 as of
from pox.core import core
from pox.lib.revent.revent import EventMixin
from pox.lib.addresses import EthAddr, IPAddr
from pox.lib.packet.ethernet import ethernet
from pox.lib.packet.arp import arp

class FakeGateway (EventMixin):
    def __init__ (self):
        core.openflow.addListeners(self)
        
    def _handle_ConnectionUp(self, event):
        pass
                       
    def _handle_PacketIn(self, event):
        packet = event.parsed

        if packet.src != EthAddr("00:11:22:33:44:55"):

            if packet.type == ethernet.ARP_TYPE:
                arp_packet = packet.find('arp')
                
                if arp_packet.opcode == arp.REQUEST:
                    # Check if the ARP request is for the IP 10.0.2.1
                    if arp_packet.protodst == IPAddr('10.0.2.1'):
                        
                        # Create the ARP reply
                        arp_reply = arp()
                        arp_reply.hwsrc = EthAddr("00:00:00:00:00:01") #eth addr of the fake gateway
                        arp_reply.hwdst = arp_packet.hwsrc
                        arp_reply.protosrc = arp_packet.protodst
                        arp_reply.protodst = arp_packet.protosrc
                        arp_reply.opcode = arp.REPLY
                        
                        # Create the Ethernet frame
                        ether_reply = ethernet()
                        ether_reply.type = ethernet.ARP_TYPE
                        ether_reply.dst = arp_packet.hwsrc
                        ether_reply.src = arp_reply.hwsrc
                        ether_reply.payload = arp_reply
                        
                        # Send the ARP reply
                        msg = of.ofp_packet_out()
                        msg.data = ether_reply.pack()
                        msg.actions.append(of.ofp_action_output(port=event.ofp.in_port))
                        event.connection.send(msg)


def launch ():
    core.registerNew(FakeGateway)