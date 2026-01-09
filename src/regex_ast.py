"""
Types representing the regex AST.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class Spanned:
    """
    Base of all AST classes, contains the span and source information for the node, along with a non-recursive __str__ and convenience length property.
    """

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start

@dataclass(frozen=True)
class RegexLiteral(Spanned):
    """
    A singular literal character.
    """
    char: str

@dataclass(frozen=True)
class AltEnd(Spanned):
    """
    The end of one Alt concatenation.
    """
    jump_to: int

@dataclass(frozen=True)
class GroupStart(Spanned):
    """
    The start of a group, used for tracking concats and where repeats should point.
    """
    group_index: int
    concat_indexes: Sequence[int]

@dataclass(frozen=True)
class GroupEnd(Spanned):
    """
    The end of a group, used for tracking where repeats should point.
    """
    group_start: int
    group_index: int

@dataclass(frozen=True)
class RepeatEnd(Spanned):
    """
    The end of a greedy repeat, matches if the repeated matched at least once.
    """
    repeat_start: int

@dataclass(frozen=True)
class RegexError(Spanned):
    """
    Never matches, produced if input has errors.
    """
    message: str

type Regex = (
    RegexLiteral
    | AltEnd
    | RepeatEnd
    | GroupStart
    | GroupEnd
    | RegexError
)

