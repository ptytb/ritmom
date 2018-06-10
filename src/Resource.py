from urllib.request import urlopen
from shutil import copyfileobj
from tempfile import NamedTemporaryFile
from os.path import exists, abspath


class Resource:

    def __init__(self, url, destination, description):
        self.url = url
        self.destination = destination
        self.description = description

    def _download(self):
        with urlopen(self) as f_src, open(self.destination, 'wb') as f_dst:
            copyfileobj(f_src, f_dst)

    def ensure(self):
        if not exists(abspath(self.destination)):
            self._download()
