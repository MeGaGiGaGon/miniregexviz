"""
Types representing the regex AST.
"""


from dataclasses import dataclass
from enum import StrEnum, nonmember
from typing import TYPE_CHECKING, Literal, NamedTuple

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

class SingleChar(NamedTuple):
    char: str
    escaped_special: bool

class CharSet(NamedTuple):
    negative: bool
    chars: str  # TODO: This will make performance sad, use something better in the future

class Backref(NamedTuple):
    type: Literal["Name", "Number"]
    group_index: int

class ShortCharSet(NamedTuple):
    type: Literal["d", "D", "s", "S", "w", "W"]


@dataclass(frozen=True)
class RegexLiteral(Spanned):
    """
    A char/set of chars/something like that for matching against the source string.
    """

    literal: SingleChar | CharSet | Backref | ShortCharSet

@dataclass(frozen=True)
class ZeroWidthRegexLiteral(Spanned):
    "Seperate from RegexLiteral because of repeatability checking"
    char: Literal["A", "b", "B", "z", "Z", "^", "$"]

@dataclass(frozen=True)
class AltEnd(Spanned):
    """
    The end of one Alt concatenation.
    """
    jump_to: int

class Capturing(NamedTuple):
    type: Literal["Numbered", "Named"]
    group_index: int
    group_name: str| None

class Noncapturing(NamedTuple):
    type: Literal["Noncapturing", "Atomic"]

class Flag(StrEnum):
    AsciiOnly = "a"
    IgnoreCase = "i"
    LocaleDependant = "L"
    MultiLine = "m"
    DotAll = "s"
    Unicode = "u"
    Verbose = "x"

    NEGATIVE = nonmember("imsv")

    @nonmember
    @staticmethod
    def has_conflict(flags: set[Flag]) -> bool:
        return (Flag.AsciiOnly in flags and Flag.LocaleDependant in flags) or (Flag.AsciiOnly in flags and Flag.Unicode in flags) or (Flag.LocaleDependant in flags and Flag.Unicode in flags)

class InlineFlags(NamedTuple):
    flags: set[Flag]
    negative: set[Flag]  # Should technically be a limited set, but we make sure of that in the parser and this types better

class Lookaround(NamedTuple):
    type: Literal["Lookahead", "Lookbehind"]
    negated: bool


@dataclass(frozen=True)
class GroupStart(Spanned):
    """
    The start of a group, used for tracking concats and where repeats should point.
    """
    type: Capturing | Noncapturing | InlineFlags | Lookaround
    concat_indexes: Sequence[int]

@dataclass(frozen=True)
class GlobalFlags(Spanned):
    flags: set[Flag]

@dataclass(frozen=True)
class Conditional(Spanned):
    group_index: int
    yes: int
    no: int | None

@dataclass(frozen=True)
class GroupEnd(Spanned):
    """
    The end of a group, used for tracking where repeats should point.
    """
    group_start: int
    group_index: int

@dataclass(frozen=True)
class RepeatStart(Spanned):
    """
    A Marker used for repeats that accept 0 repetitions.
    """
    repeat_end: int
    mode: Literal["greedy", "lazy", "possessive"]

@dataclass(frozen=True)
class RepeatEnd(Spanned):
    """
    The end of a repeat, matches if the repeated matches between minimum and maxium times.
    """
    repeat_start: int
    mode: Literal["greedy", "lazy", "possessive"]
    minimum: int
    maximum: int

@dataclass(frozen=True)
class RegexError(Spanned):
    """
    Never matches, produced if input has errors.
    """
    message: str

@dataclass(frozen=True)
class Comment(Spanned): ...

type Regex = (
    RegexLiteral
    | ZeroWidthRegexLiteral
    | AltEnd
    | GroupStart
    | GlobalFlags
    | Conditional
    | GroupEnd
    | RepeatStart
    | RepeatEnd
    | RegexError
    | Comment
)
