"""
The lexer and parser for turning a string into a regex AST.

Currently just a parser since the lexer is not needed yet.
"""


from typing import TYPE_CHECKING, Literal, TypeGuard

from src.regex_ast import (
    EOF,
    Alt,
    AltEnd,
    GroupEnd,
    GroupStart,
    Regex,
    RegexError,
    RegexLiteral,
    RepeatEnd,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class TokenGroupStart: ...
class TokenGroupEnd: ...
class TokenAltSep: ...
class TokenPlus: ...

type Token = TokenGroupStart | TokenGroupEnd | TokenAltSep | RegexLiteral | TokenPlus

def is_regex_sequence(data: Sequence[object]) -> TypeGuard[Sequence[Regex]]:
    return all(isinstance(x, Regex.__value__) for x in data)  # pyright: ignore[reportAny]

def parse(source: str) -> Sequence[Regex]:
    alt_stack: list[int] = [0]
    group_stack: list[int] = []
    source_index: int = 0
    output: list[
        Regex
        | tuple[Literal["Group"], int]
        | tuple[Literal["Alt"], int, list[int], int]
        | tuple[Literal["AltEnd"], int]
    ] = [("Alt", 0, [], 0)]
    progress_index: int = 1
    group_index: int = 0

    def get_alt_safe(pop: bool) -> tuple[int, int, list[int], int]:
        alt_index = alt_stack.pop() if pop else alt_stack[-1]
        match output[alt_index]:
            case ("Alt", start, option_indexes, progress):
                return alt_index, start, option_indexes, progress
            case _:
                raise RuntimeError("Internal Error: Index in alt_stack did not correspond to an in progress alt in output list")

    def get_group_safe(pop: bool) -> tuple[int, int]:
        group_index = group_stack.pop() if pop else group_stack[-1]
        match output[group_index]:
            case ("Group", start):
                return group_index, start
            case _:
                raise RuntimeError("Internal Error: Index in group_stack did not correspond to an in progress group in output list")

    def fix_alt_ends(option_indexes: list[int]):
        for index in option_indexes:
            match output[index - 1]:
                case ("AltEnd", start):
                    output[index - 1] = AltEnd(start, int(start + 1), source, len(output))
                case _:
                    raise RuntimeError("Internal Error: Index in alt options did not correspond to an alt end")

    for char in source:
        if char == "(":
            group_stack.append(len(output))
            output.append(("Group", source_index))
            alt_stack.append(len(output))
            output.append(("Alt", source_index + 1, [], progress_index))
            progress_index += 1
        elif char == "|":
            get_alt_safe(False)[2].append(len(output) + 1)
            output.append(("AltEnd", source_index))
        elif char == ")":
            if not group_stack:
                output.append(RegexError(source_index, source_index + 1, source, "Unopened group"))
            else:
                group_start, start = get_group_safe(True)
                output.append(GroupEnd(source_index, source_index + 1, source, group_start, group_index))
                output[group_start] = GroupStart(start, start + 1, source, group_index)
                group_index += 1
                alt_index, start, option_indexes, progress = get_alt_safe(True)
                output[alt_index] = Alt(start, source_index, source, option_indexes, progress)
                fix_alt_ends(option_indexes)
        elif char == "+":
            match output[-1]:
                case RegexLiteral(start):
                    output.append(RepeatEnd(start, source_index + 1, source, len(output)-1))
                case GroupEnd(start, group_start=group_start):
                    output.append(RepeatEnd(start, source_index + 1, source, group_start))
                case _:
                    output.append(RegexError(source_index, source_index + 1, source, "Unrepeatable item"))
        else:
            output.append(RegexLiteral(source_index, source_index + 1, source, char))
        source_index = source_index + 1
    while alt_stack:
        if group_stack:
            group_index, start = get_group_safe(True)
            output[group_index] = RegexError(start, start + 1, source, "Unclosed Group")
        alt_index, start, option_indexes, progress = get_alt_safe(True)
        output[alt_index] = Alt(start, source_index + 1, source, option_indexes, progress)
        fix_alt_ends(option_indexes)
    output.append(EOF(source_index, source_index, source))
    if is_regex_sequence(output):
        return output
    else:
        raise ValueError(f"Internal Error: Parser output has unfixed temporary values\n{output}")
