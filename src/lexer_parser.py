"""
The lexer and parser for turning a string into a regex AST.
"""


from collections.abc import Container
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NamedTuple, NewType, TypeGuard

from src.regex_ast import (
    AltEnd,
    Backref,
    Capturing,
    CharSet,
    Comment,
    Conditional,
    Flag,
    GlobalFlags,
    GroupEnd,
    GroupStart,
    InlineFlags,
    Lookaround,
    Noncapturing,
    Regex,
    RegexError,
    RegexLiteral,
    RepeatEnd,
    RepeatStart,
    ShortCharSet,
    SingleChar,
    ZeroWidthRegexLiteral,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

class GenericSpanned[T](NamedTuple):
    start: int
    end: int
    item: T

class TokenGroupEnd: ...
class TokenAlt: ...

type Token = GenericSpanned[TokenGroupEnd | TokenAlt | Capturing | Noncapturing | InlineFlags | Lookaround] | ZeroWidthRegexLiteral | Comment | RegexError | GlobalFlags | RegexLiteral

@dataclass
class SourceHandler:
    "Tracks the source in a rust-like way to prevent way too many inbounds checks"
    source: str
    index: int = 0
    stored_index: int = 0

    def next(self) -> str | None:
        if self.index < len(self.source):
            self.index += 1
            return self.source[self.index - 1]

    def peek(self) -> str | None:
        if self.index < len(self.source):
            return self.source[self.index]

    def next_if_eq(self, c: str) -> str | None:
        if self.peek() == c:
            return self.next()

    def next_if_ne(self, c: str) -> str | None:
        if self.peek() != c:
            return self.next()

    def next_if_in(self, c: Container[str]) -> str | None:
        if self.peek() in c:
            return self.next()
    
    def span(self) -> tuple[int, int]:
        stored = self.stored_index
        self.stored_index = self.index
        return stored, self.index

    def next_while_flag(self, negative: bool) -> set[Flag]:
        flags = set[Flag]()
        check = Flag.NEGATIVE if negative else Flag._value2member_map_
        while n := self.next_if_in(check):
            flags.add(Flag(n))
        return flags

def lexer(raw_source: str) -> Sequence[Token]:
    source = SourceHandler(raw_source)
    group_index = 1
    output: list[Token] = []
    while char := source.next():
        if char == "(":
            if source.next_if_eq("?"):
                if source.peek() in Flag._value2member_map_:
                    flags = source.next_while_flag(False)
                    if source.next_if_eq(")"):
                        if output:
                            output.append(RegexError(*source.span(), "Global flag groups must only be at the start of the regex"))
                        elif Flag.has_conflict(flags):
                            output.append(RegexError(*source.span(), "Flags 'a', 'u' and 'L' are incompatible"))
                        else:
                            output.append(GlobalFlags(*source.span(), flags))
                        continue
                    # if source.next_if_eq("-"):
                    #     negative = set[Flag]()
                    #     while n := source.next_if_in(Flag.NEGATIVE):
                    #         negative.add(Flag(n))
                    else:
                        unknown_index = source.index
                        while source.next_if_ne(")"):
                            pass
                        _ = source.next_if_eq(")")
                        output.append(RegexError(*source.span(), f"Unknown flag at position {unknown_index}"))
                # elif source.next_if_eq("-"):
                #     ...
                elif source.next_if_eq(":"):
                    output.append(GenericSpanned(*source.span(), Noncapturing("Noncapturing")))
            else:
                output.append(GenericSpanned(*source.span(), Capturing("Numbered", group_index, None)))
                group_index += 1
        elif char == "\\":
            ... # TODO: specials
        elif char == ")":
            output.append(GenericSpanned(*source.span(), TokenGroupEnd()))
        elif char == "|":
            output.append(GenericSpanned(*source.span(), TokenAlt()))
        else:
            output.append(RegexLiteral(*source.span(), SingleChar(char, False)))
    return output

def is_regex_sequence(data: Sequence[object]) -> TypeGuard[Sequence[Regex]]:
    return all(isinstance(x, Regex.__value__) for x in data)  # pyright: ignore[reportAny]

class InProgressGroup(NamedTuple):
    group_start_index: int
    group_index: int
    alts: list[InProgressAlt]

class InProgressAlt(NamedTuple):
    start_regex_index: int
    concat: list[Regex]

def parse(tokens: Sequence[Token]) -> Sequence[Regex]:
    if not tokens:
        return [GroupStart(0, 0, 0, [1]), GroupEnd(0, 0, 0, 0)]

    group_stack: list[InProgressGroup] = [InProgressGroup(-1, 0, [InProgressAlt(1, [])])]

    def last_concat() -> list[Regex]:
        return group_stack[-1].alts[-1].concat

    def fold_last_group(finished: bool) -> None:
        group_start_index, group_index, alts = group_stack.pop()
        concat = last_concat()
        if finished:
            concat.append(GroupStart(group_start_index, source_index + 1, group_index, [alt_start for alt_start, _ in alts[1:]]))
        else:
            concat.append(RegexError(group_start_index, group_start_index + 1, "Unclosed Group"))
        concat.extend(alts[0].concat)
        for alt_start, alt in alts[1:]:
            concat.append(AltEnd(alt_start - 1, alt_start, regex_index))
            concat.extend(alt)
        if finished:
            concat.append(GroupEnd(source_index, source_index + 1, group_start_index, group_index))

    for source_index, char in enumerate(tokens):
        regex_index = source_index + 1
        if char == "(":
            group_stack.append(InProgressGroup(source_index, group_stack[-1].group_index + 1, [InProgressAlt(regex_index + 1, [])]))
        elif char == "|":
            group_stack[-1].alts.append(InProgressAlt(regex_index + 1, []))
        elif char == ")":
            if len(group_stack) == 1:
                last_concat().append(RegexError(source_index, source_index + 1, "Unopened group"))
            else:
                fold_last_group(True)
        elif char == "+":
            concat = last_concat()
            match concat:
                case [*_, RegexLiteral(start)]:
                    concat.append(RepeatEnd(start, source_index + 1, regex_index - 1))
                case [*_, GroupEnd(start, group_start=group_start)]:
                    concat.append(RepeatEnd(start, source_index + 1, group_start + 1))
                case _:
                    concat.append(RegexError(source_index, source_index + 1, "Unrepeatable item"))
        else:
            last_concat().append(RegexLiteral(source_index, source_index + 1, char))
    while len(group_stack) > 1:
        fold_last_group(False)
    group_stack.insert(0, InProgressGroup(0, 0, [InProgressAlt(1, [])]))
    # Silly hack to make regexes like "a|" have the final AltEnd point at the final GroupEnd instead of themselves
    regex_index += 1  # pyright: ignore[reportPossiblyUnboundVariable]
    # Silly hack to make the final GroupEnd highlighting not appear on the last char
    source_index += 1  # pyright: ignore[reportPossiblyUnboundVariable]
    fold_last_group(True)
    return last_concat()
