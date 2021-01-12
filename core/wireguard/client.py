from yamlable import YamlAble, yaml_info


@yaml_info(yaml_tag_ns='')
class Client(YamlAble):

    def __init__(self, name: str, description: str, ipv4_address: str, private_key: str, public_key: str, nat: bool,
                 endpoint: str, interface: str, dns1: str, dns2: str = None):
        self.name = name
        self.description = description
        self.ipv4_address = ipv4_address
        self.private_key = private_key
        self.public_key = public_key
        self.nat = nat
        self.endpoint = endpoint
        self.interface = interface
        self.dns1 = dns1
        self.dns2 = dns2

    def __to_yaml_dict__(self):
        """ Called when you call yaml.dump()"""
        return {
            "name": self.name,
            "description": self.description,
            "ipv4_address": self.ipv4_address,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "nat": self.nat,
            "interface": self.interface,
            "dns1": self.dns1,
            "dns2": self.dns2
        }

    @staticmethod
    def from_dict(dct):
        """ This optional method is called when you call yaml.load()"""
        return Client(dct["name"], dct["description"], dct["ipv4_address"], dct["private_key"], dct["public_key"],
                      dct["nat"], "", dct["interface"], dct["dns1"], dct["dns2"])

    def generate_conf(self) -> str:
        """Generate a wireguard configuration file suitable for this client."""

        iface = f"[Interface]\n" \
                f"PrivateKey = {self.private_key}\n" \
                f"DNS = {self.dns1}"
        if self.dns2:
            iface += f", {self.dns2}"
        iface += "\n"
        iface += f"Address = {self.ipv4_address}\n\n"

        peer = f"[Peer]\n" \
               f"PublicKey = {self.public_key}\n" \
               f"AllowedIPs = {self.ipv4_address}\n" \
               f"Endpoint = {self.endpoint}\n"
        if self.nat:
            peer += "PersistentKeepalive = 25\n"

        return iface + peer
