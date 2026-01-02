from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Never, Self

def main():
    print("Hello from parser-3!")

if __name__ == "__main__":
    main()
class Ok[T]:
    def __init__(self, value: T):
        self._value: T = value
class Err[E]:
    def __init__(self, value: E):
        self._value: E = value
class Skip: ...
# type Result[T, E] = Ok[T] | Err[E]
# type ParserOutput[I, O, E] = Ok[tuple[Sequence[I], O]] | Err[E] | Skip
type ParserOutput[I, O, E] = tuple[Sequence[I], Ok[O] | Err[E]] | Skip
@dataclass(frozen=True)
class Dot:
    @classmethod
    def parse(cls, input: Sequence[str]) -> ParserOutput[str, Self, Never]:
        if input and input[0] == ".":
            return input[1:], Ok(cls())
            # return Ok((input[1:], cls()))
        else:
            return Skip()
@dataclass(frozen=True)
class Caret:
    @classmethod
    def parse(cls, input: Sequence[str]) -> ParserOutput[str, Self, Never]:
        if input and input[0] == "^":
            return input[1:], Ok(cls())
            # return Ok((input[1:], cls()))
        else:
            return Skip()
@dataclass(frozen=True)
class Dollar:
    @classmethod
    def parse(cls, input: Sequence[str]) -> ParserOutput[str, Self, Never]:
        if input and input[0] == "$":
            return input[1:], Ok(cls())
            # return Ok((input[1:], cls()))
        else:
            return Skip()
@dataclass(frozen=True)
class RegexError:
    message: str
Repeatable = RegexError | Dot | Caret | Dollar
@dataclass(frozen=True)
class Star:
    repeated: Repeatable
    @classmethod
    def parse(cls, input: Sequence[str]) -> ParserOutput[str, Self, RegexError]:
        repeated = Regex.parse(input)
        if input and input[0] == "*":
            if isinstance(repeated, Repeatable):
                return input[1:], Ok(cls(repeated))
                # return Ok((input[1:]))
            else:
                return input[1:], 
        else:
            return Skip()
@dataclass(frozen=True)
class Plus:
    repeated: Repeatable
    @classmethod
    def parse(cls, input: Sequence[str]) -> ParserOutput[str, Self, RegexError]:
        repeated = Regex.parse(input)
        if input and input[0] == "+":
            if isinstance(repeated, Repeatable):
                return input[1:], Ok(cls(repeated))
                # return Ok((input[1:]))
        else:
            return Skip()
class Regex:
    @classmethod
    def parse(cls, input: Sequence[str]) -> ParserOutput[str, Self, RegexError]:
        ...