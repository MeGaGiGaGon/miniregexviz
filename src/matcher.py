from typing import TYPE_CHECKING

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


def matches(regex: Sequence[Regex], against: str, against_index: int) -> Sequence[int | None | tuple[int, int]] | None:
    """
    Test if the regex matches starting at an index, returning the index matched to if yes, otherwise None.
    """
    backtracking_stack: list[tuple[int, int, list[int | None], list[int | None | tuple[int, int]]]] = []
    progress_trackers: list[int | None] = [None for r in regex if isinstance(r, Alt)]
    group_trackers: list[int | None | tuple[int, int]] = [None for r in regex if isinstance(r, GroupStart)]
    regex_index: int = 0
    regex_length = len(regex)
    against_length = len(against)
    starting_index = against_index

    def inc():
        nonlocal regex_index
        regex_index += 1

    while True:
        if regex_index >= regex_length:
            return [(starting_index, against_index), *group_trackers]
        match regex[regex_index]:
            case RegexLiteral(char=char):
                if against_index < against_length and char == against[against_index]:
                    inc()
                    against_index += 1
                elif backtracking_stack:
                    regex_index, against_index, progress_trackers, group_trackers = backtracking_stack.pop()
                else:
                    return None
            case Alt(option_indexes=option_indexes, progress_index=progress_index):
                last_progress = progress_trackers[progress_index]
                if last_progress is None or last_progress < against_index:
                    progress_trackers[progress_index] = against_index
                    inc()
                    backtracking_stack.extend((option, against_index, progress_trackers[::], group_trackers[::]) for option in option_indexes[::-1])
                elif backtracking_stack:
                    regex_index, against_index, progress_trackers, group_trackers = backtracking_stack.pop()
                else:
                    return None
            case AltEnd(jump_to=jump_to):
                regex_index = jump_to
            case RepeatEnd(repeat_start=repeat_start):
                inc()
                backtracking_stack.append((regex_index, against_index, progress_trackers[::], group_trackers[::]))
                regex_index = repeat_start
            case GroupStart(group_index=group_index):
                group_trackers[group_index] = against_index
                inc()
            case GroupEnd(group_index=group_index):
                match group_trackers[group_index]:
                    case int() as start:
                        group_trackers[group_index] = (start, against_index)
                    case _:
                        raise RuntimeError("Internal Error: Group tracker has non-start state while at group end")
                inc()
            case EOF():
                inc()
            case RegexError():
                return None

def scan(regex: Sequence[Regex], against: str, starting_index: int) -> Sequence[int | None | tuple[int, int]] | None:
    """
    Try to match the regex starting from the starting index. Returns the starting index and index matched until if success, otherwise None.
    """

    against_length = len(against)
    while starting_index < against_length:
        if (matched_till := matches(regex, against, starting_index)) is not None:
            return matched_till
        starting_index += 1
    return None
