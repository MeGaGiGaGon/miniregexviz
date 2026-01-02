from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
import string
from typing import Callable, Concatenate, Generic, Never, TypeVar, final, overload, override


OK_T = TypeVar("OK_T", covariant=True)


@dataclass
class Ok(Generic[OK_T]):
    value: OK_T


ERR_T = TypeVar("ERR_T", covariant=True)


@dataclass
class Err(Generic[ERR_T]):
    value: ERR_T


type Result[T, E] = Ok[T] | Err[E]


class Parser[I: Sequence[object], O, E](ABC):
    @abstractmethod
    def parse(self, input: I) -> Result[tuple[I, O], E]: ...

    # def __init_subclass__(cls) -> None:
    #     cls._parse = cls.parse
    #     def parse_wrapper(self, input: I) -> Result[tuple[I, O], E]:
    #         self.
    #     cls.parse = lambda s, x: print(f"Running parser {s.__class__.__name__} with input {x!r}") or cls._parse(s, x)

    @overload
    def repeated(self, min: None, max: int | None) -> Parser[I, Sequence[O], Never]: ...
    @overload
    def repeated(self, min: int | None, max: int | None) -> Parser[I, Sequence[O], DidNotMatchEnough[Sequence[O]]]: ...
    def repeated(self, min: int | None, max: int | None) -> Parser[I, Sequence[O], DidNotMatchEnough[Sequence[O]]]:
        return Repeated(self, min, max)

    def optional(self) -> Parser[I, O | None, Never]:
        return Optional(self)

    def map[New_O, **P](
        self,
        map_to: Callable[Concatenate[O, P], New_O],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Parser[I, New_O, E]:
        return Map(self, map_to, *args, **kwargs)

    def map_err[New_E, **P](
        self,
        map_to: Callable[Concatenate[E, P], New_E],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Parser[I, O, New_E]:
        return MapErr(self, map_to, *args, **kwargs)

    def then[O_O, O_E](self, other_parser: Parser[I, O_O, O_E]) -> Parser[I, tuple[O, O_O], E | O_E]:
        return Then(self, other_parser)

    def ignore_then[N_O, N_E](
        self, next_parser: Parser[I, N_O, N_E]
    ) -> Parser[I, N_O, E | N_E]:
        return IgnoreThen(self, next_parser)

    def then_ignore[N_O, N_E](
        self, next_parser: Parser[I, N_O, N_E]
    ) -> Parser[I, O, E | N_E]:
        return ThenIgnore(self, next_parser)
    
    def to[N_O](self, to: N_O) -> Parser[I, N_O, E]:
        return To(self, to)
    
    def err_to[N_E](self, err_to: N_E) -> Parser[I, O, N_E]:
        return ErrTo(self, err_to)


class FailedToMatch[T](Err[T]): ...


@dataclass
class just[T](Parser[Sequence[T], T, FailedToMatch[T]]):
    item: T

    @override
    def parse(self, input: Sequence[T]) -> Result[tuple[Sequence[T], T], FailedToMatch[T]]:
        if input and input[0] == self.item:
            return Ok((input[1:], input[0]))
        else:
            return Err(FailedToMatch(self.item))


@dataclass
class choice[T](Parser[Sequence[T], T, FailedToMatch[Sequence[T]]]):
    choices: Sequence[T]

    @override
    def parse(self, input: Sequence[T]) -> Result[tuple[Sequence[T], T], FailedToMatch[Sequence[T]]]:
        if input and input[0] in self.choices:
            return Ok((input[1:], input[0]))
        else:
            return Err(FailedToMatch(self.choices))


@final
class first_of[I: Sequence[object], O, E](Parser[I, O, E | None]):
    def __init__(self, *parsers: Parser[I, O, E]):
        self.parsers = parsers

    @override
    def parse(self, input: I) -> Result[tuple[I, O], E | None]:
        for parser in self.parsers:
            match parser.parse(input):
                case Ok((input, value)):
                    return Ok((input, value))
                case Err(err):
                    return Err(err)
        return Err(None)


class EOF[I: Sequence[object]](Parser[I, None, None]):
    @override
    def parse(self, input: I) -> Result[tuple[I, None], None]:
        if not input:
            return Ok((input, None))
        else:
            return Err(None)


class DidNotMatchEnough[T](Err[T]): ...

@dataclass
class Repeated[I: Sequence[object], O, E](Parser[I, Sequence[O], DidNotMatchEnough[Sequence[O]]]):
    parser: Parser[I, O, E]
    min: int | None
    max: int | None

    @override
    def parse(self, input: I) -> Result[tuple[I, Sequence[O]], DidNotMatchEnough[Sequence[O]]]:
        output: list[O] = []
        index = 0
        while True:
            if index > self.max if self.max is not None else False:
                break 
            match self.parser.parse(input):
                case Ok((input, value)):
                    output.append(value)
                case Err(value):
                    break
            index += 1
        if self.min is not None and self.min <= index:
            return Ok((input, output))
        else:
            return Err(DidNotMatchEnough(output))


@dataclass
class Optional[I: Sequence[object], O, E](Parser[I, O | None, Never]):
    parser: Parser[I, O, E]

    @override
    def parse(self, input: I) -> Result[tuple[I, O | None], Never]:
        match self.parser.parse(input):
            case Ok(value):
                return Ok(value)
            case Err(value):
                return Ok((input, None))


@final
class Map[I: Sequence[object], O, E, Old_O, **P](Parser[I, O, E]):
    def __init__(
        self,
        parser: Parser[I, Old_O, E],
        map_to: Callable[Concatenate[Old_O, P], O],
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        self.parser = parser
        self.map_to = map_to
        self.args = args
        self.kwargs = kwargs

    @override
    def parse(self, input: I) -> Result[tuple[I, O], E]:
        match self.parser.parse(input):
            case Ok((input, value)):
                return Ok((input, self.map_to(value, *self.args, **self.kwargs)))
            case Err(err):
                return Err(err)


@final
class MapErr[I: Sequence[object], O, E, Old_E, **P](Parser[I, O, E]):
    def __init__(
        self,
        parser: Parser[I, O, Old_E],
        map_to: Callable[Concatenate[Old_E, P], E],
        *args: P.args,
        **kwargs: P.kwargs,
    ):
        self.parser = parser
        self.map_to = map_to
        self.args = args
        self.kwargs = kwargs

    @override
    def parse(self, input: I) -> Result[tuple[I, O], E]:
        match self.parser.parse(input):
            case Ok((input, value)):
                return Ok((input, value))
            case Err(err):
                return Err(self.map_to(err, *self.args, **self.kwargs))


@dataclass
class Then[I: Sequence[object], L_O, R_O, L_E, R_E](Parser[I, tuple[L_O, R_O], L_E | R_E]):
    left: Parser[I, L_O, L_E]
    right: Parser[I, R_O, R_E]

    @override
    def parse(self, input: I) -> Result[tuple[I, tuple[L_O, R_O]], L_E | R_E]:
        match self.left.parse(input):
            case Ok((input, l_value)):
                match self.right.parse(input):
                    case Ok((input, r_value)):
                        return Ok((input, (l_value, r_value)))
                    case Err(err):
                        return Err(err)
            case Err(err):
                return Err(err)


@dataclass
class IgnoreThen[I: Sequence[object], L_O, R_O, L_E, R_E](Parser[I, R_O, L_E | R_E]):
    left: Parser[I, L_O, L_E]
    right: Parser[I, R_O, R_E]

    @override
    def parse(self, input: I) -> Result[tuple[I, R_O], L_E | R_E]:
        match self.left.parse(input):
            case Ok((input, _)):
                # TODO: Why can't this be returned directly?
                match self.right.parse(input):
                    case Ok((input, value)):
                        return Ok((input, value))
                    case Err(err):
                        return Err(err)
            case Err(err):
                return Err(err)


@dataclass
class ThenIgnore[I: Sequence[object], L_O, R_O, L_E, R_E](Parser[I, L_O, L_E | R_E]):
    left: Parser[I, L_O, L_E]
    right: Parser[I, R_O, R_E]

    @override
    def parse(self, input: I) -> Result[tuple[I, L_O], L_E | R_E]:
        match self.left.parse(input):
            case Ok((input, value)):
                match self.right.parse(input):
                    case Ok((input, _)):
                        return Ok((input, value))
                    case Err(err):
                        return Err(err)
            case Err(err):
                return Err(err)


@dataclass
class SeperatedBy[T, O, E](Parser[Sequence[T], Sequence[O], Never]):
    parser: Parser[Sequence[T], O, E]
    seperator: T

    @override
    def parse(self, input: Sequence[T]) -> Result[tuple[Sequence[T], Sequence[O]], Never]:
        output: list[O] = []
        while True:
            match self.parser.parse(input):
                case Ok((input, value)):
                    output.append(value)
                case Err():
                    pass
            match just(self.seperator).parse(input):
                case Ok():
                    pass
                case Err():
                    break
        return Ok((input, output))


@dataclass
class To[I: Sequence[object], O, N_O, E](Parser[I, N_O, E]):
    parser: Parser[I, O, E]
    _to: N_O
    
    @override
    def parse(self, input: I) -> Result[tuple[I, N_O], E]:
        match self.parser.parse(input):
            case Ok((input, _)):
                return Ok((input, self._to))
            case err:
                return err


@dataclass
class ErrTo[I: Sequence[object], O, E, N_E](Parser[I, O, N_E]):
    parser: Parser[I, O, E]
    _err_to: N_E
    
    @override
    def parse(self, input: I) -> Result[tuple[I, O], N_E]:
        match self.parser.parse(input):
            case Err(_):
                return Err(self._err_to)
            case ok:
                return ok


@dataclass
class ParserFunction[I: Sequence[object], O, E](Parser[I, O, E]):
    inner_function: Callable[[], Parser[I, O, E]]

    @override
    def parse(self, input: I) -> Result[tuple[I, O], E]:
        return self.inner_function().parse(input)


def parser_function[I: Sequence[object], O, E](
    func: Callable[[], Parser[I, O, E]],
) -> Parser[I, O, E]:
    """
    A decorator that turns a function that returns a parser into a parser object.

    This will delay evaluation of the function until parse time, which prevents infinite loop issue with right-recursive parsers.

    Note that this does not fix issues with left-recursive parsers, which will still make an infinite loop at parse time.
    """
    return ParserFunction(func)


class RegexItem: ...

@dataclass
class RegexError(RegexItem):
    regex: RegexItem | str
class SkipParsing: ...

@dataclass
class RegexLiteral(RegexItem):
    literal: str


@parser_function
def literals() -> Parser[Sequence[str], RegexLiteral, RegexError | SkipParsing]:
    return choice(string.ascii_letters + string.digits).err_to(SkipParsing()).map(RegexLiteral)


@dataclass
class CharSet(RegexItem):
    characters: Sequence[RegexLiteral]


@parser_function
def char_set() -> Parser[Sequence[str], CharSet, RegexError | SkipParsing]:
    return (
        just("[").err_to(SkipParsing())
        .ignore_then(just("[").map(RegexLiteral).then(literals.repeated(1, None)).err_to(RegexError("Empty charset")))
        .then_ignore(just("]").err_to(RegexError("Unclosed charset")))
        .map(lambda x: (x[0], *x[1]))
        .map(CharSet)
    )


@dataclass
class Group(RegexItem):
    regex: Alt


@parser_function
def group() -> Parser[Sequence[str], Group, RegexError | SkipParsing]:
    return just("(").err_to(SkipParsing()).ignore_then(alt).then_ignore(just(")").err_to(RegexError("UnclosedGroup"))).map(Group)


@dataclass
class Alt:
    concats: Sequence[Concat]


@parser_function
def alt() -> Parser[Sequence[str], Alt, Never]:
    return SeperatedBy(concat, "|").map(Alt)


@dataclass
class Concat:
    regexes: Sequence[RegexItem]


@parser_function
def concat() -> Parser[Sequence[str], Concat, RegexError]:
    return regex_item.repeated(None, None).map(Concat)


@parser_function
def regex_item() -> Parser[Sequence[str], RegexItem, RegexError]:
    return repeatable.then_ignore(just("+").optional())


@parser_function
def repeatable() -> Parser[Sequence[str], RegexItem, RegexError]:
    return first_of(group, char_set, literals)


def regex() -> Parser[Sequence[str], Alt, None]:
    return alt.then_ignore(EOF())


def main():
    print(regex().parse("([abc]"))


if __name__ == "__main__":
    main()
