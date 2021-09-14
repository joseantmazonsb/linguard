from typing import List


def list_to_str(_list: list, separator=", ") -> str:
    length = len(_list)
    text = ""
    count = 0
    for item in _list:
        if count < length - 1:
            text += item + separator
        else:
            text += item
        count += 1
    return text


def str_to_list(string: str, separator: str = "\n") -> List[str]:
    chunks = string.strip().split(separator)
    lst = []
    for cmd in chunks:
        lst.append(cmd)
    return lst
