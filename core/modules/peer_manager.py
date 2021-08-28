from collections import OrderedDict
from http.client import BAD_REQUEST
from random import randint
from typing import Dict
from uuid import uuid4 as gen_uuid

from core.exceptions import WireguardError
from core.models import Peer, Interface
from core.utils import generate_privkey, generate_pubkey
from web.utils import fake


def generate_peer(interface: Interface = None) -> Peer:
    uuid = gen_uuid().hex
    name = fake.name()
    description = ""
    mask = f"/{randint(8, 30)}"
    ipv4_address = fake.ipv4_private() + mask
    private_key = generate_privkey()
    public_key = generate_pubkey(private_key)
    dns1 = "8.8.8.8"
    dns2 = "8.8.4.4"
    nat = False
    peer = Peer(uuid, name, description, ipv4_address, private_key, public_key, nat, interface, dns1, dns2)
    pending_peers[peer.uuid] = peer
    return peer


def sort_peers(iface: Interface):
    sorted_peers = OrderedDict(sorted(iface.peers.items(), key=lambda t: t[1].name))
    iface.peers.clear()
    for uuid in sorted_peers:
        p = sorted_peers[uuid]
        iface.peers[uuid] = p


def add_peer(peer: Peer):
    if peer.uuid not in pending_peers:
        raise WireguardError("Invalid peer addition!", BAD_REQUEST)
    del pending_peers[peer.uuid]
    iface = peer.interface
    iface.peers[peer.uuid] = peer
    sort_peers(iface)


def edit_peer(peer: Peer, name: str, description: str, ipv4_address: str,
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


def remove_peer(peer: Peer):
    del peer.interface.peers[peer.uuid]


def get_pending_peer_by_name(name: str) -> Peer:
    for peer in pending_peers.values():
        if peer.name == name:
            return peer
    raise WireguardError(f"Unable to retrieve pending peer '{name}'!", BAD_REQUEST)


pending_peers: Dict[str, Peer]
pending_peers = OrderedDict()
