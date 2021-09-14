import os


def write_lines(content: str, path: str):
    with open(path, "w") as file:
        file.writelines(content)


def get_filename_without_extension(path: str) -> str:
    filename, extension = os.path.splitext(path)
    return os.path.basename(filename)
