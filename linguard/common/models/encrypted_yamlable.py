import os
from typing import Type

from yamlable import YamlAble, Y

from linguard.common.utils.encryption import CryptoUtils
from linguard.common.utils.system import try_makedir


class EncryptedYamlAble(YamlAble):

    def save(self, filepath: str, encryption_key: str):
        """
        Save the current instance as an encrypted yaml file.

        :param encryption_key:
        :param filepath:
        :return:
        """
        data = CryptoUtils().encrypt(self.dumps_yaml().encode(), encryption_key)
        path = os.path.abspath(filepath)
        try_makedir(os.path.dirname(path))
        with open(path, "wb") as file:
            file.write(data)

    @classmethod
    def load(cls: Type[Y], filepath: str, encryption_key: str) -> Y:
        """
        Read an encrypted yaml file and return a serialized instance of this class.

        :param encryption_key:
        :param filepath:
        :return:
        """
        with open(filepath, "rb") as file:
            yaml_str = CryptoUtils().decrypt(file.read(), encryption_key).decode()
            return cls.loads_yaml(yaml_str)