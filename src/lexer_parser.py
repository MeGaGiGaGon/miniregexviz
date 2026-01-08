"""
The lexer and parser for turning a string into a regex AST.

Currently just a parser since the lexer is not needed yet.
"""


from typing import TYPE_CHECKING, TypeGuard

from src.regex_ast import (
    AltEnd,
    GroupEnd,
    GroupStart,
    Regex,
    RegexError,
    RegexLiteral,
    RepeatEnd,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

def is_regex_sequence(data: Sequence[object]) -> TypeGuard[Sequence[Regex]]:
    return all(isinstance(x, Regex.__value__) for x in data)  # pyright: ignore[reportAny]

def parse(source: str) -> Sequence[Regex]:
    if not source:
        return [GroupStart(0, 0, "", 0, [1]), GroupEnd(0, 0, "", 0, 0)]

    group_stack: list[tuple[int, int, list[tuple[int, list[Regex]]]]] = [(-1, 0, [(1, [])])]

    def fold_last_group(finished: bool) -> None:
        group_start_index, group_index, alts = group_stack.pop()
        if finished:
            group_stack[-1][2][-1][1].append(GroupStart(group_start_index, source_index + 1, source, group_index, [alt_start for alt_start, _ in alts[1:]]))
        else:
            group_stack[-1][2][-1][1].append(RegexError(group_start_index, group_start_index + 1, source, "Unclosed Group"))
        group_stack[-1][2][-1][1].extend(alts[0][1])
        for alt_start, alt in alts[1:]:
            group_stack[-1][2][-1][1].append(AltEnd(alt_start - 1, alt_start, source, regex_index))
            group_stack[-1][2][-1][1].extend(alt)
        if finished:
            group_stack[-1][2][-1][1].append(GroupEnd(source_index, source_index + 1, source, group_start_index, group_index))

    for source_index, char in enumerate(source):
        regex_index = source_index + 1
        if char == "(":
            group_stack.append((source_index, group_stack[-1][1] + 1, [(regex_index + 1, [])]))
        elif char == "|":
            group_stack[-1][2].append((regex_index + 1, []))
        elif char == ")":
            if len(group_stack) == 1:
                group_stack[-1][2][-1][1].append(RegexError(source_index, source_index + 1, source, "Unopened group"))
            else:
                fold_last_group(True)
        elif char == "+":
            match group_stack[-1][2][-1][1]:
                case [*_, RegexLiteral(start)]:
                    group_stack[-1][2][-1][1].append(RepeatEnd(start, source_index + 1, source, regex_index - 1))
                case [*_, GroupEnd(start, group_start=group_start)]:
                    group_stack[-1][2][-1][1].append(RepeatEnd(start, source_index + 1, source, group_start + 1))
                case _:
                    group_stack[-1][2][-1][1].append(RegexError(source_index, source_index + 1, source, "Unrepeatable item"))
        else:
            group_stack[-1][2][-1][1].append(RegexLiteral(source_index, source_index + 1, source, char))
    while len(group_stack) > 1:
        fold_last_group(False)
    group_stack.insert(0, (0, 0, [(1, [])]))
    # Silly hack to make regexes like "a|" have the final AltEnd point at the final GroupEnd instead of themselves
    regex_index += 1  # pyright: ignore[reportPossiblyUnboundVariable]
    # Silly hack to make the final GroupEnd highlighting not appear on the last char
    source_index += 1  # pyright: ignore[reportPossiblyUnboundVariable]
    fold_last_group(True)
    return group_stack[-1][2][-1][1]
