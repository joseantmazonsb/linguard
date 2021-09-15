from linguard.common.utils.system import Command
from linguard.core.exceptions import WireguardError


def is_wg_iface_up(iface_name: str) -> bool:
    from linguard.core.config.wireguard import config
    return Command(f"{config.wg_bin} show {iface_name}").run_as_root().successful


def generate_privkey() -> str:
    from linguard.core.config.wireguard import config
    result = Command(f"{config.wg_bin} genkey").run_as_root()
    if not result.successful:
        raise WireguardError(result.err)
    return result.output


def generate_pubkey(privkey: str) -> str:
    from linguard.core.config.wireguard import config
    result = Command(f"echo {privkey} | sudo {config.wg_bin} pubkey").run()
    if not result.successful:
        raise WireguardError(result.err)
    return result.output


def get_wg_interface_status(name: str) -> str:
    if is_wg_iface_up(name):
        return "up"
    return "down"
