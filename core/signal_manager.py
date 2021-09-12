import signal
import sys
from logging import warning, info

from core.config.traffic_config import config
from core.cron_manager import cron_manager
from core.wireguard_manager import wireguard_manager


class SignalManager:

    def __init__(self):
        self.attached = False

    def attach(self):
        if self.attached:
            warning("Already attached!")
            return
        info("Setting up termination signal handlers...")
        signal.signal(signal.SIGINT, self.terminal_signal_handler)
        signal.signal(signal.SIGTERM, self.terminal_signal_handler)
        signal.signal(signal.SIGQUIT, self.terminal_signal_handler)
        info("Setup completed.")

    @staticmethod
    def terminal_signal_handler(sig, frame):
        warning(f"Caught termination signal {sig}. Shutting down the application...")
        cron_manager.stop()
        config.driver.update_data()
        wireguard_manager.stop()
        sys.exit()


signal_manager = SignalManager()
