"""
Types representing the regex AST.
"""


from dataclasses import dataclass
from typing import TYPE_CHECKING, override

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

    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}_{self.start}_{self.end}_{self.source[self.start:self.end]}"

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
    concats: Sequence[Concat]

@dataclass(frozen=True)
class Concat(Spanned):
    """
    A list of regex items that matches if all the items match in sequence.
    """
    regexes: Sequence[RegexItem]

@dataclass(frozen=True)
class Group(Spanned):
    """
    Both allows for repeating an alternation, and later capturing specific contents.
    """
    contents: Alt

@dataclass(frozen=True)
class Repeat(Spanned):
    """
    Greedilly repeats the repeated, matches if repeated matches at least once.
    """
    repeated: Repeatable

@dataclass(frozen=True)
class RegexError(Spanned):
    """
    Never matches, produced if input has errors.
    """
    inner: RegexItem | None | Alt
    message: str

Repeatable = Group | RegexLiteral | RegexError
type RegexItem = Group | Repeat | RegexLiteral | RegexError
type Regex = Alt | Concat | RegexItem
