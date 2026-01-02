from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import override
import typing

class Debug:
    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({", ".join(f"{k}={v}" for k, v in self.__dict__.items())})"  # pyright: ignore[reportAny]

@dataclass(frozen=True)
class Spanned:
    start: int
    end: int
    source: str

    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}_{self.start}_{self.end}_{self.source[self.start:self.end].replace(" ", "%20")}"

    @property
    def length(self) -> int:
        return self.end - self.start

@dataclass(frozen=True)
class RegexLiteral(Spanned):
    char: str

    def to_matcher(self) -> Matcher:
        # print(self)
        return Matcher(self, True, False)

class TokenGroupStart(Debug): ...
class TokenGroupEnd(Debug): ...
class TokenAltSep(Debug): ...
class TokenPlus(Debug): ...

type Token = TokenGroupStart | TokenGroupEnd | TokenAltSep | RegexLiteral | TokenPlus

def lexer(input: str) -> tuple[Sequence[Token], str]:
    index = 0
    length = len(input)
    output: list[Token] = []
    while index < length:
        char = input[index]
        if char == "(":
            output.append(TokenGroupStart())
        elif char == ")":
            output.append(TokenGroupEnd())
        elif char == "|":
            output.append(TokenAltSep())
        elif char == "+":
            output.append(TokenPlus())
        else:
            output.append(RegexLiteral(index, index + 1, input, input[index]))
        index += 1
    return output, input

@dataclass(frozen=True)
class Alt(Spanned):
    concats: Sequence[Concat]

    def to_matcher(self) -> Matcher:
        # print(self)
        if len(self.concats) == 0:
            return Matcher(("progress", 0), True, False)
        elif len(self.concats) == 1:
            return Matcher(("progress", 0), self.concats[0].to_matcher(), False)
        progress = Matcher(("progress", 0), Matcher(self, self.concats[-2].to_matcher(), self.concats[-1].to_matcher()), False)
        for concat in self.concats[:-2][::-1]:
            progress = replace(progress, left=Matcher(self, concat.to_matcher(), progress.left))
        return progress

@dataclass(frozen=True)
class Concat(Spanned):
    regexes: Sequence[RegexItem]

    def to_matcher(self) -> Matcher:
        # print(self)
        if not self.regexes:
            return Matcher(self, True, True)
        result = current = self.regexes[0].to_matcher()
        for item in self.regexes[1:]:
            # print(1, current.pp())
            item = item.to_matcher()
            stack: list[Matcher] = [current]
            seen = set[int]()

            while stack:
                current = stack.pop()
                # print(2, current.pp())
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
            current = item
        # print(1, current.pp())
        return result

@dataclass(frozen=True)
class Group(Spanned):
    contents: Alt

    def to_matcher(self) -> Matcher:
        # print(self)
        return self.contents.to_matcher()

@dataclass(frozen=True)
class Repeat(Spanned):
    repeated: Repeatable

    def to_matcher(self) -> Matcher:
        repeated = self.repeated.to_matcher()
        repeat = Matcher(self, repeated, True)
        stack = [repeated]
        seen = {id(repeat)}

        while stack:
            current = stack.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            if current.left is True:
                current.left = repeat
            elif current.left is not False:
                stack.append(current.left)

            if current.right is True:
                current.right = repeat
            elif current.right is not False:
                stack.append(current.right)
        return repeated

@dataclass(frozen=True)
class RegexError(Spanned):
    inner: RegexItem | None | Alt
    message: str

    def to_matcher(self) -> Matcher:
        # print(self)
        return Matcher(self, False, False)

type RegexItem = Group | Repeat | RegexLiteral | RegexError
Repeatable = Group | RegexLiteral | RegexError
type Regex = Alt | Concat | RegexItem

def parser(tokens: Sequence[Token], source: str) -> Alt:
    index = 0
    span_index = 0
    group_stack: list[tuple[list[Concat], list[RegexItem], int]] = []
    length = len(tokens)
    concat_storage: list[Concat] = []
    current_concat: list[RegexItem] = []

    def push_current_concat_to_storage():
        nonlocal concat_storage, current_concat, span_index
        if len(current_concat) > 0:
            concat_storage.append(Concat(current_concat[0].start, current_concat[-1].end, source, current_concat))
        else:
            concat_storage.append(Concat(span_index, span_index, source, current_concat))
        current_concat = []

    while index < length:
        match tokens[index]:
            case RegexLiteral() as literal:
                current_concat.append(literal)
                span_index += literal.length
            case TokenPlus():
                if len(current_concat) > 0:
                    for_inspection = current_concat.pop()
                    if isinstance(for_inspection, Repeatable):
                        current_concat.append(Repeat(for_inspection.start, for_inspection.end + 1, source, for_inspection))
                    else:
                        current_concat.append(for_inspection)
                        current_concat.append(RegexError(span_index, span_index + 1, source, None, "Repeat with invalid element to repeat"))
                else:
                    current_concat.append(RegexError(span_index, span_index + 1, source, None, "Repeat with nothing to repeat"))
                span_index += 1
            case TokenAltSep():
                push_current_concat_to_storage()
                span_index += 1
            case TokenGroupStart():
                group_stack.append((concat_storage, current_concat, span_index))
                concat_storage = []
                current_concat = []
                span_index += 1
            case TokenGroupEnd():
                if not group_stack:
                    current_concat.append(RegexError(span_index, span_index + 1, source, None, "Unopened group"))
                    span_index += 1
                else:
                    push_current_concat_to_storage()
                    stored_concat_storage, stored_current_concat, stored_span_index = group_stack.pop()
                    stored_current_concat.append(Group(stored_span_index, span_index + 1, source, Alt(concat_storage[0].start, concat_storage[-1].end, source, concat_storage)))
                    concat_storage = stored_concat_storage
                    current_concat = stored_current_concat
                    span_index += 1
        index += 1
    push_current_concat_to_storage()
    while group_stack:        
        stored_concat_storage, stored_current_concat, stored_span_index = group_stack.pop()
        stored_current_concat.append(RegexError(stored_span_index, span_index, source, Alt(concat_storage[0].start, concat_storage[-1].end, source, concat_storage), "Unclosed group"))
        concat_storage = stored_concat_storage
        current_concat = stored_current_concat
        push_current_concat_to_storage()
    return Alt(concat_storage[0].start, concat_storage[-1].end, source, concat_storage)

@dataclass
class Matcher:
    operation: Regex | tuple[typing.Literal["progress"], int]
    left: Matcher | bool
    right: Matcher | bool

    @override
    def __str__(self) -> str:
        return f"Matcher_{id(self)%10000:04d}_{str(self.operation).replace(" ", "%20").replace("(", "%o").replace(")", "%c")}"

    def pp(self, indent: int=0, seen: set[int] | None = None) -> str:
        if seen is None:
            seen = set()
        if id(self) in seen:
            return f"{"  "*indent}<{self}>"
        else:
            seen.add(id(self))
            return f"""{"  "*indent}{self} (
{"  "*(indent:=indent+1)}{self.operation},
{self.left.pp(indent, seen) if isinstance(self.left, Matcher) else f"{"  "*indent}{self.left}"},
{self.right.pp(indent, seen) if isinstance(self.right, Matcher) else f"{"  "*indent}{self.right}"},
{"  "*(indent:=indent-1)})"""

    def mermaid(self, seen: set[int] | None = None) -> str:
        start = ""
        if seen is None:
            seen = set()
            start = "flowchart TD\n"
        if id(self) in seen:
            return f"{self}"
        else:
            seen.add(id(self))
            return (f"""{start}{self}-->{self.left}
{self}-->{self.right}"""
 + ("\n" + self.left.mermaid(seen) if isinstance(self.left, Matcher) and id(self.left) not in seen else "")
 + ("\n" + self.right.mermaid(seen) if isinstance(self.right, Matcher) and id(self.right) not in seen else ""))

    def fix_progress_indexes(self, seen: set[int] | None = None, counter: int=0) -> int:
        if seen is None:
            seen = set()
        if id(self) in seen:
            return counter
        seen.add(id(self))
        match self.operation:
            case ("progress", _):
                self.operation = ("progress", counter)
                counter += 1
            case _: pass
        if not isinstance(self.left, bool):
            counter = self.left.fix_progress_indexes(seen, counter)
        if not isinstance(self.right, bool):
            counter = self.right.fix_progress_indexes(seen, counter)
        return counter

    def matches(self, input: str, index: int = 0, progress: list[int] | None = None) -> bool:
        # print(self)
        if not progress:
            progress = [index-1 for _ in range(self.fix_progress_indexes())]

        match self.operation:
            case RegexError():
                return False
            case RegexLiteral(char=char):
                if index < len(input) and input[index] == char:
                    if isinstance(self.left, bool):
                        return self.left
                    else:
                        return self.left.matches(input, index + 1, progress[::])
                elif isinstance(self.right, bool):
                    return self.right
                else:
                    return self.right.matches(input, index + 1, progress[::])
            case Alt() | Group() | Repeat() | Concat():
                if isinstance(self.left, bool):
                    return self.left
                elif self.left.matches(input, index, progress[::]):
                    return True
                elif isinstance(self.right, bool):
                    return self.right
                else:
                    return self.right.matches(input, index, progress[::])
            case ("progress", progress_index):
                if index <= progress[progress_index]:
                    return False
                progress[progress_index] = index
                if isinstance(self.left, bool):
                    return self.left
                elif self.left.matches(input, index, progress[::]):
                    return True
                elif isinstance(self.right, bool):
                    return self.right
                else:
                    return self.right.matches(input, index, progress[::])



re = parser(*lexer("("*100 + "x" + ")" * 100))
# print(repr(re))
# print()
m = re.to_matcher()
# print(m.pp())
# print()
print(m.matches("x"))
# print()
# print(m.mermaid())
