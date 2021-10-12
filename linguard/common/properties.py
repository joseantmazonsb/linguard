import os


class Properties:

    def __init__(self):
        self.dev_env = False
        self.workdir = ""
        self.setup_required = True
        self.setup_filename = ".setup"

    def join_workdir(self, path: str) -> str:
        """
        Prepend the current workdir to the given path.

        :param path:
        :return:
        """
        return os.path.join(self.workdir, path)

    @property
    def setup_filepath(self):
        return self.join_workdir(self.setup_filename)

    def setup_file_exists(self):
        return os.path.exists(self.setup_filepath)


global_properties = Properties()

