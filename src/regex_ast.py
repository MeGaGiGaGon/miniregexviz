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
    source: str

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
class Alt(Spanned):
    """
    A series of concatenations to be tried until the first matches.
    """
    option_indexes: Sequence[int]
    progress_index: int

@dataclass(frozen=True)
class AltEnd(Spanned):
    """
    The end of one Alt concatenation.
    """
    jump_to: int

@dataclass(frozen=True)
class GroupStart(Spanned):
    """
    The start of a group, used for tracking where repeats should point.
    """

@dataclass(frozen=True)
class GroupEnd(Spanned):
    """
    The end of a group, used for tracking where repeats should point.
    """
    group_start: int

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

@dataclass(frozen=True)
class EOF(Spanned):
    """
    Represents the end of the input, used to have a valid end index to point to.
    """

type Regex = (
    RegexLiteral
    | Alt
    | AltEnd
    | RepeatEnd
    | GroupStart
    | GroupEnd
    | RegexError
    | EOF
)

