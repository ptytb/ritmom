from abc import abstractmethod
from copy import copy
from typing import List


class BaseFilter:

    @abstractmethod
    def __call__(self, chunk):
        ...

    @staticmethod
    def _duplicate_chunk(chunk):
        return copy(chunk)
