import os


class Properties:
    def __init__(self):
        self.dev_env = False
        self.workdir = ""
        self.setup_required = True

    def join_workdir(self, path: str) -> str:
        """
        Prepend the current workdir to the given path.

        :param path:
        :return:
        """
        return os.path.join(self.workdir, path)


global_properties = Properties()
SETUP_FILENAME = ".setup"
