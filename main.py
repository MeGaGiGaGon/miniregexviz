from collections.abc import Sequence
from copy import copy
from dataclasses import dataclass
from typing import Literal, NewType

@dataclass
class Split:
    reason: Literal["|", "+"]
    greedy: RegexIndex
    lazy: RegexIndex

@dataclass
class Item:
    char: str
    matches: RegexIndex
    fails: RegexIndex

@dataclass
class Progress:
    index: ProgressIndex
    matches: RegexIndex
    fails: RegexIndex

type Regex = Sequence[Item | Split | bool | Progress]
InputIndex = NewType("InputIndex", int)
RegexIndex = NewType("RegexIndex", int)
ProgressIndex = NewType("ProgressIndex", int)
ProgressTracker = NewType("ProgressTracker", list[None | InputIndex])

def matches(regex: Regex, input: str, regex_index: RegexIndex = RegexIndex(0)) -> bool:  # pyright: ignore[reportCallInDefaultInitializer]
    stack: list[tuple[InputIndex, RegexIndex, ProgressTracker]] = []
    progress_tracker: ProgressTracker = ProgressTracker([None for op in regex if isinstance(op, Progress)])

    index = InputIndex(0)

    while True:
        current = regex[regex_index]
        print(index, regex_index, current, progress_tracker, stack)
        match current:
            case Item():
                regex_index = current.matches if input[index] == current.char else current.fails
            case Progress():
                last_index = progress_tracker[current.index]
                if last_index is None or index > last_index:
                    progress_tracker[current.index] = index
                    regex_index = current.matches
                else:
                    regex_index = current.fails
            case Split():
                stack.append((index, current.lazy, copy(progress_tracker)))
                regex_index = current.greedy
            case False:
                if stack:
                    index, regex_index, progress_tracker = stack.pop()
            case True:
                return True

# print(matches([True, False, Progress(0, 3, 1), Split("|", 4, 5), Item("a", 5, 1), Split("+", 2, 0)], "x", 2))
