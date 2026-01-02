from collections.abc import Sequence
from dataclasses import dataclass

@dataclass
class Literal:
    char: str

    def to_matcher(self) -> Char:
        return Char(None, None, self.char)

@dataclass
class Repeat:
    repeated: Repeatable

    def to_matcher(self) -> Parseable:
        repeated = self.repeated.to_matcher()

        split = Split(repeated, None)

        stack: list[Parseable] = [repeated]
        seen = set[Parseable]()

        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)

            if current.matches is None:
                current.matches = split
            else:
                stack.append(current.matches)
        
        return repeated

@dataclass
class Alt:
    concats: Sequence[Concat]

    def to_matcher(self) -> Progress:
        if len(self.concats) == 0:
            return Progress(Succeed(None, None), None, 0)
        elif len(self.concats) == 1:
            return Progress(self.concats[0].to_matcher(), Fail(None, None), 0)
        split = Split(None, None)
        progress = Progress(split, None, 0)
        for concat in self.concats:
            split.matches = concat.to_matcher()
            new_split = Split(None, None)
            split.fails = new_split
            split = new_split
        
        return progress

@dataclass
class Concat:
    concated: Sequence[RegexItem]

    def to_matcher(self) -> Parseable:
        if not self.concated:
            return Succeed(None, None)
        result = outer = self.concated[0].to_matcher()
        for concat in self.concated[1:]:
            concat = concat.to_matcher()
            stack: list[Parseable] = [concat]
            seen = set[Parseable]()
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                if current.matches is None:
                    current.matches = outer
                else:
                    stack.append(current.matches)
            outer = concat
        return result

@dataclass
class Group:
    inner: Alt

    def to_matcher(self) -> Progress:
        return self.inner.to_matcher()

type Repeatable = Literal | Group
type RegexItem = Repeatable | Repeat

@dataclass
class Base:
    matches: Parseable | None
    fails: Parseable | None
@dataclass
class Char(Base):
    char: str
class Split(Base): ...
class Fail(Base): ...
class Succeed(Base): ...
@dataclass
class Progress(Base):
    last: int
type Parseable = Char | Split | Progress | Fail | Succeed

print(Alt([Concat([Repeat(Literal("a"))])]).to_matcher())