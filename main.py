"""
class Literal = ...
class Repeat = (Group | Literal) _'+'
class Group = _'(' Alt _')'
class Alt = Concat.seperated_by('|')
class Concat = Regex*
class Regex = Repeat | Literal
"""

from dataclasses import dataclass
from typing import Self

@dataclass
class Error:
    regex: None
    start: int
    end: int
    message: str

@dataclass
class Literal:
    char: str
    start: int
    end: int

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int] | None:
        if index < len(input):
            return cls(input[index], index, index + 1), index + 1
        else:
            return None

@dataclass
class Repeat:
    repeated: Literal | Group
    start: int
    end: int

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self | Error, int] | None:
        result = Group.parse(input, index)
        if result is None:
            result = Literal.parse(input, index)
            if result is None:
                return Error(None, index, index + 1, "Repeat with nothing to repeat"), index + 1
        repeated, new_index = result
        if input[new_index] == "+":
            return cls(repeated, index, new_index + 1), new_index + 1
        else:
            return None

@dataclass
class Group:
    grouped: Alt
    start: int
    end: int

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int] | None:
        raise NotImplementedError

@dataclass
class Alt:
    start: int
    end: int

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int] | None:
        raise NotImplementedError

@dataclass
class Concat:
    start: int
    end: int

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int] | None:
        raise NotImplementedError

@dataclass
class Regex:
    start: int
    end: int

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int] | None:
        raise NotImplementedError