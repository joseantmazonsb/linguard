from datetime import timedelta, datetime
from ipaddress import IPv4Address
from threading import Thread
from time import sleep
from typing import Dict

from linguard.core.config.web import config


class Client:
    def __init__(self, ip: IPv4Address):
        self.ip = ip
        self.login_attempts = 0
        self.banned_until = datetime.now()

    @staticmethod
    def __sleep__():
        sleep(config.login_ban_time)

    def ban(self):
        self.login_attempts = 0
        self.banned_until = datetime.now() + timedelta(seconds=config.login_ban_time)
        Thread(target=self.__sleep__, daemon=True).start()

    def is_banned(self):
        return self.banned_until > datetime.now()


clients: Dict[IPv4Address, Client] = {}
