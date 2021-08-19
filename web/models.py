import os.path
from typing import Type, Dict, Any
from uuid import uuid4 as gen_uuid

from flask_login import logout_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from yamlable import YamlAble, yaml_info, Y

from core.crypto_utils import CryptoUtils
from core.utils import try_makedir


@yaml_info(yaml_tag='user')
class User(UserMixin, YamlAble):
    HASHING_METHOD = "pbkdf2:sha256"

    def __init__(self, name: str):
        self.id = gen_uuid().hex
        self.name = name
        self.__password = None
        self.__authenticated = False

    def __str__(self):
        return {
            "id": self.id,
            "name": self.name,
            "authenticated": self.__authenticated
        }.__str__()

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, value: str):
        self.__password = generate_password_hash(str(value), self.HASHING_METHOD)

    def __to_yaml_dict__(self):
        """ Called when you call yaml.dump()"""
        return {
            "id": self.id,
            "name": self.name,
            "password": self.password,
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        u = User(dct["name"])
        u.id = dct["id"]
        u.__password = str(dct["password"])
        return u

    def login(self, password) -> bool:
        if self.is_authenticated:
            return True
        self.__authenticated = check_password_hash(self.password, password)
        return self.__authenticated

    def logout(self):
        self.__authenticated = False
        return logout_user()

    @property
    def is_authenticated(self):
        return self.__authenticated


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


@yaml_info(yaml_tag='users')
class UserDict(Dict[str, User], EncryptedYamlAble):

    def get_by_name(self, name: str):
        for k, v in self.items():
            if v.name == name:
                return v
        return None

    def set_contents(self, dct: "UserDict"):
        """
        Clear the dictionary and fill it with the values of the given one.

        :param dct:
        :return:
        """
        self.clear()
        self.update(dct)

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return self

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        u = UserDict()
        u.update(dct)
        return u


users = UserDict()
