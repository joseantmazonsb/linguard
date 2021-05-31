from collections import OrderedDict
from random import randint
from uuid import uuid4 as gen_uuid

from faker import Faker

from core.modules.key_manager import KeyManager
from core.wireguard import Peer, Interface


class PeerManager:

    def __init__(self, endpoint: str, key_manager: KeyManager, faker: Faker):
        self.endpoint = endpoint
        self.key_manager = key_manager
        self.faker = faker

    def generate_peer(self, interface: Interface = None) -> Peer:
        uuid = gen_uuid().hex
        name = self.faker.name()
        description = ""
        mask = f"/{randint(8, 30)}"
        ipv4_address = self.faker.ipv4_private() + mask
        private_key = self.key_manager.generate_privkey()
        public_key = self.key_manager.generate_pubkey(private_key)
        dns1 = "8.8.8.8"
        dns2 = "8.8.4.4"
        nat = False
        peer = Peer(uuid, name, description, ipv4_address, private_key, public_key, nat, interface, self.endpoint,
                    dns1, dns2)
        return peer

    @staticmethod
    def add_peer(peer: Peer):
        iface = peer.interface
        iface.peers[peer.uuid] = peer
        sorted_peers = OrderedDict(sorted(iface.peers.items()))
        iface.peers.clear()
        for uuid in sorted_peers:
            p = sorted_peers[uuid]
            iface.peers[uuid] = p

    def edit_peer(self, peer: Peer, name: str, description: str, ipv4_address: str,
                       iface: Interface, dns1: str, nat: bool, dns2: str = ""):
        peer.name = name
        peer.interface = iface
        peer.description = description
        peer.ipv4_address = ipv4_address
        peer.dns1 = dns1
        if dns2:
            peer.dns2 = dns2
        peer.nat = nat
        peer.interface.peers = OrderedDict(sorted(peer.interface.peers.items()))

    def remove_peer(self, peer: Peer):
        del peer.interface.peers[peer.uuid]
