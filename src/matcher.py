from typing import TYPE_CHECKING, NamedTuple

from src.regex_ast import (
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


class Backtracker(NamedTuple):
    regex_index: int
    against_index: int
    group_starts: list[int]
    group_ends: list[int]


def matches(regex: Sequence[Regex], against: str, against_index: int) -> tuple[Sequence[tuple[int, int]] | None, list[str]]:
    """
    Test if the regex matches starting at an index, returning the index matched to if yes, otherwise None.
    """
    backtracking_stack: list[Backtracker] = []
    group_starts: list[int] = [-1 for r in regex if isinstance(r, GroupStart)]
    group_ends: list[int] = [-1 for r in regex if isinstance(r, GroupStart)]
    regex_index: int = 0
    regex_length = len(regex)
    against_length = len(against)
    debug_output: list[str] = []

    def inc():
        nonlocal regex_index
        regex_index += 1

    while True:
        debug_output.append(f"{against_index}r{regex_index} s{group_starts} e[{group_ends}] b{backtracking_stack}")
        if regex_index >= regex_length:
            return [*zip(group_starts, group_ends)], debug_output
        match regex[regex_index]:
            case RegexLiteral(char=char):
                if against_index < against_length and char == against[against_index]:
                    inc()
                    against_index += 1
                elif backtracking_stack:
                    regex_index, against_index, group_starts, group_ends = backtracking_stack.pop()
                else:
                    return None, debug_output
            case GroupStart(concat_indexes=option_indexes, group_index=group_index):
                if group_starts[group_index] < against_index:
                    group_starts[group_index] = against_index
                    inc()
                    backtracking_stack.extend(Backtracker(option, against_index, group_starts[::], group_ends[::]) for option in option_indexes[::-1])
                elif backtracking_stack:
                    regex_index, against_index, group_starts, group_ends = backtracking_stack.pop()
                else:
                    return None, debug_output
            case AltEnd(jump_to=jump_to):
                regex_index = jump_to
            case RepeatEnd(repeat_start=repeat_start):
                inc()
                backtracking_stack.append(Backtracker(regex_index, against_index, group_starts[::], group_ends[::]))
                regex_index = repeat_start
            case GroupEnd(group_index=group_index):
                group_ends[group_index] = against_index
                inc()
            case RegexError():
                return None, debug_output

def scan(regex: Sequence[Regex], against: str, starting_index: int) -> tuple[Sequence[tuple[int, int]] | None, list[str]]:
    """
    Try to match the regex starting from the starting index. Returns the starting index and index matched until if success, otherwise None.
    """

    debug_output: list[str] = []
    against_length = len(against)
    while starting_index < against_length:
        result, match_debug = matches(regex, against, starting_index)
        debug_output.extend(match_debug)
        if result is None:
            debug_output.append(f"Matching failed at starting index {starting_index}")
        else:
            debug_output.append(f"Match found at starting index {starting_index}")
            return result, debug_output
        starting_index += 1
    return None, debug_output
