import string
from dataclasses import dataclass
from collections.abc import Callable, Sequence
from typing import assert_type, overload, reveal_type, Self
class Parser[I, O]:
    def __init__(self, processor: Callable[[Sequence[I]], tuple[Sequence[I], O]]):
        self._processor: Callable[[Sequence[I]], tuple[Sequence[I], O]] = processor
    def parse(self, input: Sequence[I]) -> tuple[Sequence[I], O]:
        return self._processor(input)
    
    def map[U](self: Parser[I, O | None], mapper: Callable[[O], U]) -> Parser[I, U | None]:
        def inner(input: Sequence[I]) -> tuple[Sequence[I], U | None]:
            input, result = self._processor(input)
            if result is None:
                return input, None
            else:
                return input, mapper(result)
        return Parser(inner)
    def spanned(self) -> Parser[I, tuple[int, O]]:
        def inner(input: Sequence[I]) -> tuple[Sequence[I], tuple[int, O]]:
            l = len(input)
            input, result = self._processor(input)
            return input, (l - len(input), result)
        return Parser(inner)
def just[I](item: I) -> Parser[I, I | None]:
    def inner(input: Sequence[I]) -> tuple[Sequence[I], I | None]:
        if input[0] == item:
            return input[1:], item
        else:
            return input, None
    return Parser(inner)
def any_of[I](items: Sequence[I]) -> Parser[I, I | None]:
    def inner(input: Sequence[I]) -> tuple[Sequence[I], I | None]:
        if input[0] in items:
            return input[1:], input[0]
        else:
            return input, None
    return Parser(inner)
@dataclass
class RegexLiteral:
    char: str
    @classmethod
    def parser(cls) -> Parser[str, Self | None]:
        return Parser[str, str].map(any_of(string.ascii_letters), cls)
@dataclass
class RegexError:
    data: Regex | None
    message: str
    @classmethod
    def parser(cls)
@dataclass
class Repeat:
    repeated: Regex
@dataclass
class Regex:
    ...