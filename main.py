from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from typing import (
    Any,
    Callable,
    Concatenate,
    Never,
    overload,
    override,
    final
)

type SuperNeverCallable = (
    Callable[[], object]
    | Callable[[Never], object]
    | Callable[[Never, Never], object]
    | Callable[[Never, Never, Never], object]
)

@final
class Ok[T]:
    __match_args__ = ("_value",)

    def __init__(self, value: T):
        self._value = value

    @override
    def __repr__(self) -> str:
        return f"Ok({self._value!r})"

    def is_ok(self) -> bool:
        return True

    def unwrap_or_default(self, _default: object) -> T:
        return self._value

    def map_ok[U](self, func: Callable[[T], U]) -> Ok[U]:
        return Ok(func(self._value))

    def star_map_ok[U, *TS](self: Ok[tuple[*TS]], func: Callable[[*TS], U]) -> Ok[U]:
        return Ok(func(*self._value))

    def flatten[O, E](self: Result[Result[O, E], E]) -> Result[O, E]:
        match self:
            case Ok(inner):
                return inner
            case err:
                return err


@final
class Err[E]:
    __match_args__ = ("_value",)

    def __init__(self, value: E):
        self._value = value

    @override
    def __repr__(self) -> str:
        return f"Err({self._value!r})"

    def is_ok(self) -> bool:
        return False

    def unwrap_or_default[D](self, default: D) -> D:
        return default

    def map_ok[U](self, _func: SuperNeverCallable) -> Err[E]:
        return self

    def star_map_ok[U, *TS](self, _func: SuperNeverCallable) -> Err[E]:
        return self

    def flatten[T](self: Result[Result[T, E], E]) -> Result[T, E]:
        match self:
            case Ok(inner):
                return inner
            case err:
                return err


type Result[O, E] = Ok[O] | Err[E]

type ParserOutput[I, O, E] = Result[tuple[Sequence[I], O], E]


type ParserFunction[I, O, E] = Callable[[Sequence[I]], ParserOutput[I, O, E]]


class bind[T](partial[T]):
    """
    An improved version of partial which accepts Ellipsis (...) as a placeholder
    """

    @override
    def __call__(self, /, *args: Any, **keywords: Any) -> T:  # pyright: ignore[reportExplicitAny, reportAny]
        keywords = {**self.keywords, **keywords}
        iargs = iter(args)
        args = (next(iargs) if arg is ... else arg for arg in self.args)  # pyright: ignore[reportAny, reportAssignmentType]
        return self.func(*args, *iargs, **keywords)


def find_name(func: Callable[..., object]) -> str:
    if isinstance(func, bind):
        extra_name: list[str] = []
        for arg in func.args:  # pyright: ignore[reportAny]
            if isinstance(arg, Parser) or arg == ...:
                continue
            if hasattr(arg, "__name__"):  # pyright: ignore[reportAny]
                extra_name.append(arg.__name__)  # pyright: ignore[reportAny]
            else:
                extra_name.append(repr(arg))  # pyright: ignore[reportAny]
        extra = ", ".join(extra_name)
        return func.func.__name__ + (" " + extra if extra else "")
    else:
        if hasattr(func, "__name__"):
            return func.__name__
        else:
            return repr(func)


indentation = 0


def trace_args[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> T:
        global indentation
        print("  " * indentation, find_name(func), args, kwargs)
        indentation += 1
        output = func(*args, **kwargs)
        indentation -= 1
        print("  " * indentation, output)
        return output

    return inner


def parser_maker[I, O, E, **P](
    processor: Callable[Concatenate[Sequence[I], P], ParserOutput[I, O, E]],
) -> Callable[P, Parser[I, O, E]]:
    def made_parser(*args: P.args, **kwargs: P.kwargs) -> Parser[I, O, E]:
        return Parser(trace_args(bind(processor, ..., *args, **kwargs)))

    return made_parser


def method_parser_maker[S, I, O, E, **P](
    processor: Callable[Concatenate[S, Sequence[I], P], ParserOutput[I, O, E]],
) -> Callable[Concatenate[S, P], Parser[I, O, E]]:
    def made_parser(self: S, *args: P.args, **kwargs: P.kwargs) -> Parser[I, O, E]:
        return Parser(trace_args(bind(processor, self, ..., *args, **kwargs)))

    return made_parser


class Parser[I, O, E]:
    _processor: ParserFunction[I, O, E]

    def __init__(self, processor: ParserFunction[I, O, E]):
        self._processor = processor

    def parse(self, input: Sequence[I]) -> ParserOutput[I, O, E]:
        return self._processor(input)

    @method_parser_maker
    def then[OTHER_O, OTHER_E](
        self, input: Sequence[I], other: Parser[I, OTHER_O, OTHER_E]
    ) -> ParserOutput[I, tuple[O, OTHER_O], E | OTHER_E]:
        return (
            self.parse(input)
            .star_map_ok(
                lambda input, self_output: other.parse(input).star_map_ok(
                    lambda input, other_output: (input, (self_output, other_output))
                )
            )
            .flatten()
        )

    @method_parser_maker
    def then_ignore[OTHER_O, OTHER_E](
        self, input: Sequence[I], other: Parser[I, OTHER_O, OTHER_E]
    ) -> ParserOutput[I, O, E | OTHER_E]:
        return (
            self.parse(input)
            .star_map_ok(
                lambda input, self_output: other.parse(input).star_map_ok(
                    lambda input, _: (input, self_output)
                )
            )
            .flatten()
        )

    @method_parser_maker
    def ignore_then[OTHER_O, OTHER_E](
        self, input: Sequence[I], other: Parser[I, OTHER_O, OTHER_E]
    ) -> ParserOutput[I, OTHER_O, E | OTHER_E]:
        return (
            self.parse(input)
            .star_map_ok(
                lambda input, _: other.parse(input).star_map_ok(
                    lambda input, other_output: (input, other_output)
                )
            )
            .flatten()
        )

    @method_parser_maker
    def map_output[New_O](
        self, input: Sequence[I], mapping: Callable[[O], New_O]
    ) -> ParserOutput[I, New_O, E]:
        return self.parse(input).star_map_ok(
            lambda input, value: (input, mapping(value))
        )

    @method_parser_maker
    def map_ok_output[New_O, S_T, S_E](
        self: Parser[I, Result[S_T, S_E], E],
        input: Sequence[I],
        mapping: Callable[[S_T], New_O],
    ) -> ParserOutput[I, Result[New_O, S_E], E]:
        match self.parse(input):
            case Ok((input, value)):
                match value:
                    case Ok(inner_value):
                        return Ok((input, Ok(mapping(inner_value))))
                    case err:
                        return Ok((input, err))
            case err:
                return err

    @method_parser_maker
    def map_output_and_err[New_O, New_E](
        self,
        input: Sequence[I],
        mapping: Callable[[Result[O, E]], Result[New_O, New_E]],
    ) -> ParserOutput[I, New_O, New_E]:
        match self.parse(input):
            case Ok((input, value)):
                result = mapping(Ok(value))
            case err:
                result = mapping(err)
        return result.map_ok(lambda new_value: (input, new_value))

    @method_parser_maker
    def star_map_output[New_O, *TS](
        self: Parser[I, tuple[*TS], E],
        input: Sequence[I],
        mapping: Callable[[*TS], New_O],
    ) -> ParserOutput[I, New_O, E]:
        return self.parse(input).star_map_ok(
            lambda input, value: (input, mapping(*value))
        )

    @overload
    @method_parser_maker
    def repeated(
        self, input: Sequence[I], min: None, max: int | None
    ) -> ParserOutput[I, Sequence[O], Never]: ...
    @overload
    @method_parser_maker
    def repeated(
        self, input: Sequence[I], min: int | None, max: int | None
    ) -> ParserOutput[I, Sequence[O], Sequence[O]]: ...
    @method_parser_maker
    def repeated(
        self, input: Sequence[I], min: int | None, max: int | None
    ) -> ParserOutput[I, Sequence[O], Sequence[O]]:
        output: list[O] = []
        index = 0
        while True:
            if index > max if max is not None else False:
                break
            match self.parse(input):
                case Ok((input, value)):
                    output.append(value)
                case Err(value):
                    break
            index += 1
        if min is None or min <= index:
            return Ok((input, output))
        else:
            return Err(output)

    @method_parser_maker
    def optional(self, input: Sequence[I]) -> ParserOutput[I, O | None, Never]:
        match self.parse(input):
            case Ok() as ok:
                return ok
            case Err():
                return Ok((input, None))

    @method_parser_maker
    def err_to[U](self, input: Sequence[I], to: U) -> ParserOutput[I, O, U]:
        match self.parse(input):
            case Ok() as ok:
                return ok
            case Err():
                return Err(to)

    @method_parser_maker
    def seperated_by(
        self, input: Sequence[I], seperator: I
    ) -> ParserOutput[I, Sequence[O], Never]:
        output: list[O] = []
        while True:
            match self.parse(input):
                case Ok((input, value)):
                    output.append(value)
                case Err():
                    break
            match just(seperator).parse(input):
                case Ok((input, _)):
                    pass
                case Err():
                    break
        return Ok((input, output))

    @method_parser_maker
    def on_error[OTHER_O, OTHER_E](
        self, input: Sequence[I], other: Parser[I, OTHER_O, OTHER_E]
    ) -> ParserOutput[I, O | OTHER_O, OTHER_E]:
        match self.parse(input):
            case Ok() as ok:
                return ok
            case Err():
                return other.parse(input)
    
    @method_parser_maker
    def spanned(self, input: Sequence[I]) -> ParserOutput[I, tuple[Sequence[I], O], E]:
        match self.parse(input):
            case Ok((new_input, value)):
                return Ok((new_input, (input[:len(input) - len(new_input)], value)))
            case Err()as err:
                return err


@parser_maker
def just[I](input: Sequence[I], item: I) -> ParserOutput[I, I, None]:
    if input and input[0] == item:
        return Ok((input[1:], item))
    else:
        return Err(None)


@parser_maker
def choice[I](input: Sequence[I], choices: Sequence[I]) -> ParserOutput[I, I, None]:
    if input and input[0] in choices:
        return Ok((input[1:], input[0]))
    else:
        return Err(None)


@parser_maker
def first_of[I, O, E](
    input: Sequence[I], *parsers: Parser[I, O, E]
) -> ParserOutput[I, O, E | None]:
    for parser in parsers:
        match parser.parse(input):
            case Ok((input, value)):
                return Ok((input, value))
            case _err:
                pass
    return Err(None)


@parser_maker
def eof[I](input: Sequence[I]) -> ParserOutput[I, None, None]:
    if not input:
        return Ok((input, None))
    else:
        return Err(None)

def spanned[I, O, E, **P](func: Callable[Concatenate[Sequence[I], P], ParserOutput[I, O, E]]) -> Callable[Concatenate[Sequence[I], P], ParserOutput[I, tuple[Sequence[I], O], E]]:
    def wrapper(input: Sequence[I], *args: P.args, **kwargs: P.kwargs) -> ParserOutput[I, tuple[Sequence[I], O], E]:
        match func(input, *args, **kwargs):
            case Ok((new_input, value)):
                return Ok((new_input, (input[:len(input)-len(new_input)], value)))
            case Err() as err:
                return err
    return wrapper

@dataclass
class RegexItem:
    span: Sequence[str]


@dataclass
class RegexError(RegexItem):
    regex: RegexItem | str


def move_regex_error_to_output[T](
    parser_result: Result[T, RegexError],
) -> Result[T | RegexError, Never]:
    match parser_result:
        case Ok() as ok:
            return ok
        case Err(err):
            return Ok(err)


@dataclass
class SkipParsing: ...


@dataclass
class RegexLiteral(RegexItem):
    literal: str


@dataclass
class CharSet(RegexItem):
    inverted: bool
    characters: Sequence[RegexLiteral]


def regex_error_to_ok(err: object):
    if isinstance(err, RegexError):
        return Ok(err)
    else:
        return Err(err)


@parser_maker
def char_set(
    input: Sequence[str],
) -> ParserOutput[str, Result[CharSet, RegexError], SkipParsing]:
    orig_input = input 
    match just("[").parse(input):
        case Ok((input, _)):
            match just("^").parse(input):
                case Ok((input, _)):
                    inverse = True
                case Err():
                    inverse = False
            match just("]").spanned().parse(input):
                case Ok((input, c)):
                    contents = [RegexLiteral(*c)]
                case Err():
                    contents = []
            while True:
                match just("]").parse(input):
                    case Ok((input, _)):
                        return Ok((input, Ok(CharSet(orig_input[:len(orig_input) - len(input)], inverse, contents))))
                    case Err():
                        pass

                if input:
                    contents.append(RegexLiteral(input[0], input[0]))
                    input = input[1:]
                else:
                    return Ok((input, Err(RegexError("", CharSet(orig_input[:len(orig_input) - len(input)], inverse, contents)))))
        case Err():
            return Err(SkipParsing())


@dataclass
class Group(RegexItem):
    regex: Alt


@parser_maker
def group(
    input: Sequence[str],
) -> ParserOutput[str, Result[Group, RegexError], SkipParsing]:
    match just("(").spanned().parse(input):
        case Ok((input, (span1, _))):
            match alt().spanned().parse(input):
                case Ok((input, (span2, value))):
                    match just(")").spanned().parse(input):
                        case Ok((input, (span3, _))):
                            return Ok((input, Ok(Group((*span1, *span2, *span3), value))))
                        case Err():
                            return Ok((input, Err(RegexError((*span1, *span2), Group((*span1, *span2), value)))))
                case Err():
                    assert False, "Unreachable"
        case Err():
            return Err(SkipParsing())


@dataclass
class Alt:
    span: Sequence[str]
    concats: Sequence[Concat]


@parser_maker
def alt(input: Sequence[str]) -> ParserOutput[str, Alt, Never]:
    return concat().seperated_by("|").spanned().star_map_output(Alt).parse(input)


@dataclass
class Concat:
    span: Sequence[str]
    regexes: Sequence[Result[RegexItem, RegexError]]


@parser_maker
def concat(input: Sequence[str]) -> ParserOutput[str, Concat, RegexError]:
    return regex_item().repeated(None, None).spanned().star_map_output(Concat).parse(input)


@parser_maker
def regex_item(
    input: Sequence[str],
) -> ParserOutput[str, Result[RegexItem, RegexError], SkipParsing | None]:
    return repeatable().then_ignore(just("+").optional()).parse(input)


@parser_maker
def unopened_errors(input: Sequence[str]) -> ParserOutput[str, RegexError, None]:
    if input and input[0] in ")]":
        return Ok((input[1:], RegexError(input[0], input[0])))
    else:
        return Err(None)


@parser_maker
def get_next_nonspecial_char(input: Sequence[str]) -> ParserOutput[str, str, None]:
    if input and input[0] not in "|)]":
        return Ok((input[1:], input[0]))
    else:
        return Err(None)


@parser_maker
def repeatable(
    input: Sequence[str],
) -> ParserOutput[str, Result[RegexItem, RegexError], SkipParsing]:
    return (
        first_of(group(), char_set(), unopened_errors().map_output(Ok).err_to(SkipParsing()))
        .on_error(
            get_next_nonspecial_char().spanned().star_map_output(RegexLiteral).map_output(Ok).err_to(SkipParsing())
        )
        .err_to(SkipParsing())
        .parse(input)
    )


@parser_maker
def regex(input: Sequence[str]) -> ParserOutput[str, Alt, None]:
    return alt().then_ignore(eof()).parse(input)


def main():
    print(regex().parse("a+"))


if __name__ == "__main__":
    main()
