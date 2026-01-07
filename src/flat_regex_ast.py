from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NewType, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Sequence

RegexIndex = NewType("RegexIndex", int)
SourceIndex = NewType("SourceIndex", int)

@dataclass(frozen=True)
class Spanned:
    """
    Base of all AST classes, contains the span and source information for the node, along with a non-recursive __str__ and convenience length property.
    """

    start: SourceIndex
    end: SourceIndex
    source: str

    @property
    def length(self) -> int:
        return self.end - self.start

@dataclass(frozen=True)
class ReLiteral(Spanned):
    char: str

@dataclass(frozen=True)
class Alt(Spanned):
    option_indexes: list[RegexIndex]
    progress_index: int

@dataclass(frozen=True)
class AltEnd(Spanned):
    jump_to: RegexIndex

@dataclass(frozen=True)
class RepeatEnd(Spanned):
    repeat_start: RegexIndex

@dataclass(frozen=True)
class GroupStart(Spanned): ...

@dataclass(frozen=True)
class GroupEnd(Spanned):
    group_start: RegexIndex

@dataclass(frozen=True)
class ReError(Spanned):
    message: str

@dataclass(frozen=True)
class EOF(Spanned): ...

type Regex = (
    ReLiteral
    | Alt
    | AltEnd
    | RepeatEnd
    | GroupStart
    | GroupEnd
    | ReError
    | EOF
)

"""
(x+)+y|z

a[0]   g[]  a
a[0 2] g[2] a   (
a[0 2] g[2] a   ( a x
a[0 2] g[2] a   ( a x +2
a[0]   g[]  a   ( a x +2 e6 )2
a[0]   g[]  a   ( a x +2 e6 )2 +2
a[0]   g[]  a   ( a x +2 e6 )2 +2 y
a[0]   g[]  a10 ( a x +2 e6 )2 +2 y e
a[0]   g[]  a10 ( a x +2 e6 )2 +2 y e   z
a[0]   g[]  a10 ( a x +2 e6 )2 +2 y e12 z f

(x|y|())
a[0    ] g[   ] a
a[0 2  ] g[2  ] a (
a[0 2  ] g[2  ] a ( a    x
a[0 2  ] g[2  ] a ( a3   x e
a[0 2  ] g[2  ] a ( a3   x e   y
a[0 2  ] g[2  ] a ( a3,5 x e   y e
a[0 2 8] g[2 8] a ( a3,5 x e   y e   ( a
a[0 2  ] g[2  ] a ( a3,5 x e   y e   ( a )8
a[0    ] g[   ] a ( a3,5 x e11 y e11 ( a )8 )2
a[     ] g[   ] a ( a3,5 x e11 y e11 ( a )8 )2 f

"""

def is_regex_sequence(data: Sequence[object]) -> TypeGuard[Sequence[Regex]]:
    return all(isinstance(x, Regex.__value__) for x in data)  # pyright: ignore[reportAny]

def parse(source: str) -> Sequence[Regex]:
    alt_stack: list[RegexIndex] = [RegexIndex(0)]
    group_stack: list[RegexIndex] = []
    source_index: SourceIndex = SourceIndex(0)
    output: list[
        Regex
        | tuple[Literal["Group"], SourceIndex]
        | tuple[Literal["Alt"], SourceIndex, list[RegexIndex], int]
        | tuple[Literal["AltEnd"], SourceIndex]
    ] = [("Alt", SourceIndex(0), [], 0)]
    progress_index: int = 1

    def get_alt_safe(pop: bool) -> tuple[RegexIndex, SourceIndex, list[RegexIndex], int]:
        alt_index = alt_stack.pop() if pop else alt_stack[-1]
        match output[alt_index]:
            case ("Alt", start, option_indexes, progress):
                return alt_index, start, option_indexes, progress
            case _:
                raise RuntimeError("Internal Error: Index in alt_stack did not correspond to an in progress alt in output list")

    def get_group_safe(pop: bool) -> tuple[RegexIndex, SourceIndex]:
        group_index = group_stack.pop() if pop else group_stack[-1]
        match output[group_index]:
            case ("Group", start):
                return group_index, start
            case _:
                raise RuntimeError("Internal Error: Index in group_stack did not correspond to an in progress group in output list")

    def fix_alt_ends(option_indexes: list[RegexIndex]):
        for index in option_indexes:
            match output[index - 1]:
                case ("AltEnd", start):
                    output[index - 1] = AltEnd(start, SourceIndex(start + 1), source, RegexIndex(len(output)))
                case _:
                    raise RuntimeError("Internal Error: Index in alt options did not correspond to an alt end")

    for char in source:
        if char == "(":
            group_stack.append(RegexIndex(len(output)))
            output.append(("Group", source_index))
            alt_stack.append(RegexIndex(len(output)))
            output.append(("Alt", SourceIndex(source_index + 1), [], progress_index))
            progress_index += 1
        elif char == "|":
            get_alt_safe(False)[2].append(RegexIndex(len(output) + 1))
            output.append(("AltEnd", source_index))
        elif char == ")":
            if not group_stack:
                output.append(ReError(source_index, SourceIndex(source_index + 1), source, "Unopened group"))
            else:
                group_start, start = get_group_safe(True)
                output.append(GroupEnd(source_index, SourceIndex(source_index + 1), source, group_start))
                output[group_start] = GroupStart(start, SourceIndex(start + 1), source)
                alt_index, start, option_indexes, progress = get_alt_safe(True)
                output[alt_index] = Alt(start, SourceIndex(source_index), source, option_indexes, progress)
                fix_alt_ends(option_indexes)
        elif char == "+":
            match output[-1]:
                case ReLiteral(start):
                    output.append(RepeatEnd(start, SourceIndex(source_index + 1), source, RegexIndex(len(output)-1)))
                case GroupEnd(start, group_start=group_start):
                    output.append(RepeatEnd(start, SourceIndex(source_index + 1), source, group_start))
                case _:
                    output.append(ReError(source_index, SourceIndex(source_index + 1), source, "Unrepeatable item"))
        else:
            output.append(ReLiteral(source_index, SourceIndex(source_index + 1), source, char))
        source_index = SourceIndex(source_index + 1)
    while alt_stack:
        if group_stack:
            group_index, start = get_group_safe(True)
            output[group_index] = ReError(start, SourceIndex(start + 1), source, "Unclosed Group")
        alt_index, start, option_indexes, progress = get_alt_safe(True)
        output[alt_index] = Alt(start, SourceIndex(source_index + 1), source, option_indexes, progress)
        fix_alt_ends(option_indexes)
    output.append(EOF(SourceIndex(source_index - 1), SourceIndex(source_index - 1), source))
    if is_regex_sequence(output):
        return output
    else:
        raise ValueError(f"Internal Error: Parser output has unfixed temporary values\n{output}")

def matches(regex: Sequence[Regex], against: str) -> int | None:
    for i, r in enumerate(regex):
        print(i, r)
    backtracking_stack: list[tuple[RegexIndex, int, list[int | None]]] = []
    progress_trackers: list[int | None] = [None for r in regex if isinstance(r, Alt)]
    regex_index = RegexIndex(0)
    regex_length = len(regex)
    against_index = 0
    against_length = len(against)

    def inc():
        nonlocal regex_index
        regex_index = RegexIndex(regex_index + 1)

    while True:
        print(regex_index, against_index, progress_trackers, backtracking_stack)
        if regex_index >= regex_length:
            return against_index
        match regex[regex_index]:
            case ReLiteral(char=char):
                if against_index < against_length and char == against[against_index]:
                    inc()
                    against_index += 1
                elif backtracking_stack:
                    regex_index, against_index, progress_trackers = backtracking_stack.pop()
                else:
                    return False
            case Alt(option_indexes=option_indexes, progress_index=progress_index):
                last_progress = progress_trackers[progress_index]
                if last_progress is None or last_progress < against_index:
                    progress_trackers[progress_index] = against_index
                    inc()
                    backtracking_stack.extend((option, against_index, progress_trackers[::]) for option in option_indexes[::-1])
                elif backtracking_stack:
                    regex_index, against_index, progress_trackers = backtracking_stack.pop()
                else:
                    return False
            case AltEnd(jump_to=jump_to):
                regex_index = jump_to
            case RepeatEnd(repeat_start=repeat_start):
                inc()
                backtracking_stack.append((regex_index, against_index, progress_trackers[::]))
                regex_index = repeat_start
            case GroupStart() | GroupEnd() | EOF():
                inc()
            case ReError():
                return False

print(*enumerate(parse("a|")), sep="\n")
print(matches(parse("(x+)+y"), "xx"))