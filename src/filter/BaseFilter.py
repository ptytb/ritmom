from abc import abstractmethod
from copy import copy
from typing import List


class BaseFilter:
    def __init__(self):
        self.enabled = True

    @abstractmethod
    def __call__(self, chunk):
        ...

    @staticmethod
    def _duplicate_chunk(chunk):
        return copy(chunk)
