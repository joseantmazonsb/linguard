from core.exceptions import WireguardError
from core.utils import generate_privkey, generate_pubkey


class KeyManager:

    def __init__(self, wg_bin: str):
        self.wg_bin = wg_bin

    def generate_privkey(self) -> str:
        result = generate_privkey(self.wg_bin)
        if not result.successful:
            raise WireguardError(result.err)
        return result.output

    def generate_pubkey(self, privkey: str) -> str:
        result = generate_pubkey(self.wg_bin, privkey)
        if not result.successful:
            raise WireguardError(result.err)
        return result.output