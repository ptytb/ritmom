from abc import abstractmethod


class BaseFilter:

    @abstractmethod
    def apply(self, *, printable):
        ...
