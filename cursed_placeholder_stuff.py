# from expression import Result

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import partial
import inspect
from pprint import pp
import traceback
from typing import Any, Callable, ClassVar, Concatenate, Final, Literal, Never, cast, final, overload, override

class _Placeholder:
    def __init__(self):
        frame_stack = inspect.stack()
        if not frame_stack:
            raise RuntimeError("Your python implementation does not support stack frames (inspect.stack() returned no frames)")
        if len(frame_stack) < 3:
            raise RuntimeError("Tried to use Placeholder at top level, only usage inside classes is supported")
        object.__setattr__(self, "error", RuntimeError(f"Tried to use Placeholder object. Containing class is most likely missing fix_class_placeholders decorator (or the decorator has a bug).\n{"\n".join(traceback.format_stack(frame_stack[2].frame))}"))
    
    def __call__(self, *_args: object, **_kwargs: object) -> Never:
        raise self.error

    def __getattr__(self, name: str, /) -> Never:
        raise self.error

    @override
    def __setattr__(self, name: str, value: object, /) -> Never:
        raise self.error

class S[T]:

    def __new__(cls) -> type[T]:
        return _Placeholder()  # pyright: ignore[reportReturnType]

def fix_object[T: type, O](cls: T, obj: O, seen: list[object]) -> O | T:
    if isinstance(obj, _Placeholder):
        return cls

    if obj in seen:
        return obj

    seen.append(obj)

    if inspect.isfunction(obj):
        if obj.__closure__ is not None:
            for cell in obj.__closure__:
                cell.cell_contents = fix_object(cls, cell.cell_contents, seen)  # pyright: ignore[reportAny]

    if hasattr(obj, "__dict__"):
        to_set: dict[str, object] = {}
        for name, item in vars(obj).items():  # pyright: ignore[reportAny]
            if (new := fix_object(cls, item, seen)) is not item:  # pyright: ignore[reportAny]
                to_set[name] = new
        for name, item in to_set.items():
            setattr(obj, name, item)
    
    if isinstance(obj, partial):
        _, _, s = obj.__reduce__()
        f, old, k, n = s
        obj.__setstate__((f, tuple(fix_object(cls, x, seen) for x in old), k, n))  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    return obj  # pyright: ignore[reportUnknownVariableType]
def fix_class_placeholders[T: type](cls: T) -> T:
    return fix_object(cls, cls, [])


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

    @override
    def __eq__(self, value: object, /) -> bool:
        match value:
            case Ok(value):
                return self._value == value
            case _:
                return False

    def is_ok(self) -> bool:
        return True

    def is_ok_and(self, test: Callable[[T], bool]) -> bool:
        return test(self._value)

    def is_err(self) -> bool:
        return False

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
    
    def err_to(self, _to: Never) -> Ok[T]:
        return self


@final
class Err[E]:
    __match_args__ = ("_value",)

    def __init__(self, value: E):
        self._value = value

    @override
    def __repr__(self) -> str:
        return f"Err({self._value!r})"

    @override
    def __eq__(self, value: object, /) -> bool:
        match value:
            case Err(value):
                return self._value == value
            case _:
                return False

    def is_ok(self) -> bool:
        return False

    def is_ok_and(self, _test: SuperNeverCallable) -> bool:
        return False

    def is_err(self) -> bool:
        return True

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
    
    def err_to[U](self, to: U) -> Err[U]:
        return Err(to)


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


def get_dunder_name_or_repr(obj: Any) -> str:  # pyright: ignore[reportExplicitAny, reportAny]
    if hasattr(obj, "__name__"):  # pyright: ignore[reportAny]
        return str(obj.__name__)  # pyright: ignore[reportAny]
    else:
        return repr(obj)  # pyright: ignore[reportAny]


def find_name(func: Callable[..., object]) -> str:
    if isinstance(func, bind):
        extra_name: list[str] = []
        for arg in func.args:  # pyright: ignore[reportAny]
            if isinstance(arg, Parser) or arg == ...:
                continue
            extra_name.append(get_dunder_name_or_repr(arg))
        extra = ", ".join(extra_name)
        return get_dunder_name_or_repr(func.func) + (" " + extra if extra else "")
    else:
        return get_dunder_name_or_repr(func)


indentation = 0


def trace_args[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> T:
        global indentation
        print("  " * indentation, find_name(func), args, kwargs)
        # print("  " * indentation, func, args, kwargs)
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
    def map_output[New_O](
        self, input: Sequence[I], mapping: Callable[[O], New_O]
    ) -> ParserOutput[I, New_O, E]:
        return self.parse(input).star_map_ok(
            lambda input, value: (input, mapping(value))
        )

@parser_maker
def just[I](input: Sequence[I], item: I) -> ParserOutput[I, I, None]:
    if input and input[0] == item:
        return Ok((input[1:], item))
    else:
        return Err(None)

@final
@dataclass
class One:
    value: str
    parser: ClassVar = just("1").map_output(S["One"]())

import sys
fix_object(sys.modules[__name__])
# import code
# code.interact()

print(One.parser.parse("1"))
# class A: ...
# class B(A): ...

# def foo() -> A:
#     return B()
b: complex | int
def foo(x: type[int | str]): ...