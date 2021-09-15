from datetime import datetime
from typing import Type, Dict, Any, Mapping
from uuid import uuid4 as gen_uuid

from flask_login import logout_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from yamlable import YamlAble, yaml_info, Y

from linguard.common.models.encrypted_yamlable import EncryptedYamlAble
from linguard.common.models.enhanced_dict import EnhancedDict, K, V


@yaml_info(yaml_tag='user')
class User(UserMixin, YamlAble):
    HASHING_METHOD = "pbkdf2:sha256"
    login_date: datetime

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

    def login(self, password: str) -> bool:
        if self.is_authenticated:
            return True
        self.__authenticated = self.check_password(password)
        if self.__authenticated:
            self.login_date = datetime.now()
        return self.__authenticated

    def check_password(self, password: str) -> bool:
        """Check if the specified password matches the user's password without triggering a proper login."""
        return check_password_hash(self.password, password)

    def logout(self):
        self.__authenticated = False
        return logout_user()

    @property
    def is_authenticated(self):
        return self.__authenticated


@yaml_info(yaml_tag='users')
class UserDict(EnhancedDict, EncryptedYamlAble, Mapping[K, V]):

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

    def sort(self, order_by=lambda pair: pair[1].name):
        super(UserDict, self).sort(order_by)


users: UserDict[str, User]
users = UserDict()
