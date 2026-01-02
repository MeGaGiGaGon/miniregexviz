"""
Miniminiregex:
literals: `a-zA-Z0-9`
repeats: `+` only
groups: `()` numbered only
"""

"""
literal = a-zA-Z0-9

"""

from collections.abc import Sequence
from dataclasses import dataclass
import string
from typing import Self

@dataclass
class Data:
    inner: str
    current_index: int
    span_stack: list[Span]

    def push_span(self):
        self.span_stack.append(Span(self.current_index, self.current_index))

    def pop_span(self) -> Span:
        return self.span_stack.pop()

    def increment(self, by: int = 1):
        self.current_index += by
        self.span_stack[-1].end += self.current_index

    def next_if_in(self, to_check: str) -> str | None:
        if self.inner[self.current_index] in to_check:
            self.increment()
            return self.inner[self.current_index - 1]

@dataclass
class Span:
    start: int
    end: int

@dataclass
class Error:
    data_to_render: Regex | None
    message: str
    span: Span

@dataclass
class Literal:
    char: str
    span: Span

    @classmethod
    def parse(cls, data: Data) -> tuple[Self, int] | None:
        data.push_span()
        if char := data.next_if_in(string.ascii_letters + string.digits):
            return cls(char, data.pop_span()), data.current_index
        else:
            _ = data.pop_span()
            return None

@dataclass
class Repeat:
    repeated: Regex
    span: Span

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self | Error, int] | None:
        match Regex.parse(input, index):
            case None:
                if input[index] == "+":
                    return Error(None, "Repeat with nothing to repeat", Span(index, index + 1)), index + 1
                else:
                    return None
            case (regex, new_index):
                if input[index] == "+":
                    return cls(regex, Span(index, new_index + 1)), new_index + 1
                else:
                    return None

@dataclass
class Group:
    contents: Concat
    span: Span

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self | Error, int] | None:
        if input[index] == "(":
            contents, new_index = Concat.parse(input, index + 1)
            if input[new_index] == ")":
                return cls()
        else:
            return None

@dataclass
class Concat:
    regexes: Sequence[Regex]
    span: Span

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int]:
        raise NotImplementedError

@dataclass
class Regex:

    @classmethod
    def parse(cls, input: str, index: int) -> tuple[Self, int] | None:
        raise NotImplementedError