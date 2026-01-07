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


def matches(regex: Sequence[Regex], against: str) -> int | None:
    backtracking_stack: list[tuple[int, int, list[int | None]]] = []
    progress_trackers: list[int | None] = [None for r in regex if isinstance(r, Alt)]
    regex_index: int = 0
    regex_length = len(regex)
    against_index = 0
    against_length = len(against)

    def inc():
        nonlocal regex_index
        regex_index += 1

    while True:
        if regex_index >= regex_length:
            return against_index
        match regex[regex_index]:
            case RegexLiteral(char=char):
                if against_index < against_length and char == against[against_index]:
                    inc()
                    against_index += 1
                elif backtracking_stack:
                    regex_index, against_index, progress_trackers = backtracking_stack.pop()
                else:
                    return None
            case Alt(option_indexes=option_indexes, progress_index=progress_index):
                last_progress = progress_trackers[progress_index]
                if last_progress is None or last_progress < against_index:
                    progress_trackers[progress_index] = against_index
                    inc()
                    backtracking_stack.extend((option, against_index, progress_trackers[::]) for option in option_indexes[::-1])
                elif backtracking_stack:
                    regex_index, against_index, progress_trackers = backtracking_stack.pop()
                else:
                    return None
            case AltEnd(jump_to=jump_to):
                regex_index = jump_to
            case RepeatEnd(repeat_start=repeat_start):
                inc()
                backtracking_stack.append((regex_index, against_index, progress_trackers[::]))
                regex_index = repeat_start
            case GroupStart() | GroupEnd() | EOF():
                inc()
            case RegexError():
                return None
