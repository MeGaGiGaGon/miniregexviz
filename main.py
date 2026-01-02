from dataclasses import dataclass
from typing import final


@final
@dataclass
class SExpr:
    operation: Regex
    left: SExpr | None
    right: SExpr | None


@final
@dataclass
class Alt: ...


@final
@dataclass
class Concat: ...


@final
@dataclass
class RegexLiteral:
    char: str


@final
@dataclass
class Repeat: ...


@final
@dataclass
class Group: ...


# (x+|ab|c)+
# (Alt 
#   (Concat 
#       (Repeat 
#           (Group 
#               (Alt 
#                   (Repeat 
#                       (Alt 
#                           (Contact x /) 
#                       /) 
#                   /) 
#                   (Alt)
#               ) 
#           /) 
#       /) 
#   /) 
# /)

type Repeatable = RegexLiteral | Group
type RegexItem = Repeatable | Repeat
type Regex = RegexItem | Concat | Alt

def matches(regex: SExpr, input: str, index: int) -> int | None:
    stack = []
    
    match regex.operation:
        case RegexLiteral():
            return index + 1 if index < len(input) and input[index] == regex.operation.char else None
        case Group():
            assert regex.left
            return matches(regex.left, input, index)
        case Alt():
            return regex.left is None or matches(regex.left, input, index) or (regex.right is not None and matches(regex.right, input, index))
        case Repeat():
            stack = []
            while True:


