"""
The lexer and parser for turning a string into a regex AST.
"""


from typing import TYPE_CHECKING

from src.regex_ast import (
    Alt,
    Concat,
    Group,
    RegexError,
    RegexItem,
    RegexLiteral,
    Repeat,
    Repeatable,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class TokenGroupStart: ...
class TokenGroupEnd: ...
class TokenAltSep: ...
class TokenPlus: ...

type Token = TokenGroupStart | TokenGroupEnd | TokenAltSep | RegexLiteral | TokenPlus

def lexer(input: str) -> Sequence[Token]:
    """
    Takes in an input string and returns the tokenized token sequence.
    """
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
    return output

def parser(tokens: Sequence[Token], source: str) -> Alt:
    """
    Takes in a sequence of tokens and returns the AST representing the regex.
    """
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

def to_regex_ast(input: str) -> Alt:
    """
    Convenience method for converting an input directly to its AST.
    """
    return parser(lexer(input), input)
