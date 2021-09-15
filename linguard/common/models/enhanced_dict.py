from typing import Mapping, Dict, TypeVar

K = TypeVar('K')
V = TypeVar('V')


class EnhancedDict(Dict, Mapping[K, V]):

    def set_contents(self, dct: "EnhancedDict"):
        """
        Clear the dictionary and fill it with the values of the given one.

        :param dct:
        :return:
        """
        self.clear()
        self.update(dct)

    def sort(self, order_by):
        self.set_contents(EnhancedDict(sorted(self.items(), key=order_by)))

    def get_key_by_attr(self, attr: str, attr_value: str) -> K:
        """
        Get the first key (or None) of the dictionary which contains an attribute whose value is equal to attr_value.

        :param attr: Attribute to compare.
        :param attr_value: Value to compare.
        :return: The first matching key or None.
        """
        return next(iter(filter(lambda k: k.__getattribute__(attr) == attr_value, self.keys())), None)

    def get_value_by_attr(self, attr: str, attr_value: str) -> V:
        """
        Get the first value (or None) of the dictionary which contains an attribute whose value is equal to attr_value.

        :param attr: Attribute to compare.
        :param attr_value: Value to compare.
        :return: The first matching value or None.
        """
        return next(iter(filter(lambda v: v.__getattribute__(attr) == attr_value, self.values())), None)