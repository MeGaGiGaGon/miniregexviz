"""
Todo.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.regex_ast import Alt, Concat, Group, Regex, RegexError, RegexLiteral, Repeat

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class MatchLiteral:
    char: str
    matches: int | bool
    fails: int | bool

@dataclass
class Split:
    greedy: int | bool
    lazy: int | bool

@dataclass
class Progress:
    index: int
    matches: int | bool
    fails: int | bool

@dataclass
class Simple:
    next: int | bool

type Matcher = MatchLiteral | Split | Progress | Simple


def to_matcher(regex: Regex) -> Sequence[Matcher]:
    """
    Transform any regex item into a matcher.
    """
    match regex:
        case Alt():
            return alt_to_matcher(regex)
        case Group():
            return alt_to_matcher(regex.contents)
        case Repeat() | Concat():
            raise NotImplementedError
        case RegexLiteral():
            return [MatchLiteral(regex.char, True, False)]
        case RegexError():
            return [Simple(False)]



def alt_to_matcher(alt: Alt) -> Sequence[Matcher]:
    if len(alt.concats) == 0:
        return [Progress(0, True, False)]
    elif len(alt.concats) == 1:
        return [Progress(0, concat_to_matcher(alt.concats[0]), False)]
        return cls(("progress", 0), cls.concat_to_matcher(alt.concats[0]), False)
    progress = cls(("progress", 0), cls(alt, cls.concat_to_matcher(alt.concats[-2]), cls.concat_to_matcher(alt.concats[-1])), False)
    for concat in alt.concats[:-2][::-1]:
        progress.left = cls(alt, cls.concat_to_matcher(concat), progress.left)
    return progress

def replace_trues_with(self, index: int) -> Sequence[Matcher]:
    stack: list[Self] = [self]
    seen = set[int]()

    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        
        if current.left is True:
            current.left = item
        elif current.left is not False:
            stack.append(current.left)

        if current.right is True:
            current.right = item
        elif current.right is not False:
            stack.append(current.right)


def concat_to_matcher(concat: Concat) -> Sequence[Matcher]:
    if not concat.regexes:
        return cls(concat, True, True)
    result = current = cls.to_matcher(concat.regexes[0])
    for item in concat.regexes[1:]:
        item = cls.to_matcher(item)
        current.replace_trues_with(item)
        current = item
    return result

