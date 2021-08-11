import base64
import random
import string

from cryptography.fernet import Fernet


class CryptoUtils:

    __magic = "Alonso"
    KEY_LEN = 32

    def __init__(self):
        self.__magic = "Alonso"

    def encrypt(self, data: bytes, key: str) -> bytes:
        return self.__magic.encode() + Fernet(base64.b64encode(key.encode())).encrypt(data)

    def decrypt(self, data: bytes, key: str) -> bytes:
        return Fernet(base64.b64encode(key.encode())).decrypt(data[len(self.__magic):])

    def is_encrypted(self, data: bytes):
        return data[:len(self.__magic)] != self.__magic

    @classmethod
    def generate_key(cls) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=cls.KEY_LEN))
