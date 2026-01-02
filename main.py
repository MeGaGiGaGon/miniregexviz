import logging
import sys
import tkinter as tk
from copy import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NewType, final, override

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger()
_old_debug = logger.debug
def _new_debug(*inputs: object) -> None:
    inputs = list(inputs)  # pyright: ignore[reportAssignmentType]
    inputs[0] = inputs[0][:-1]  # pyright: ignore[reportIndexIssue]
    _old_debug(" ".join(str(x) for x in inputs))
logger.debug = _new_debug  # pyright: ignore[reportAttributeAccessIssue]

class Debug:
    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({", ".join(f"{k}={v}" for k, v in self.__dict__.items())})"  # pyright: ignore[reportAny]

@dataclass
class Spanned:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start

indent = 0
@dataclass
class RegexLiteral(Spanned):
    char: str

    def to_matcher(self) -> MatchRegex:
        return [Item(self.char, RegexIndex(1), RegexIndex(2)), True, False]

class TokenGroupStart(Debug): ...
class TokenGroupEnd(Debug): ...
class TokenAltSep(Debug): ...
class TokenPlus(Debug): ...

type Token = TokenGroupStart | TokenGroupEnd | TokenAltSep | RegexLiteral | TokenPlus

def lexer(input: str) -> Sequence[Token]:
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
            output.append(RegexLiteral(index, index + 1, input[index]))
        index += 1
    return output

@dataclass
class Alt(Spanned):
    concats: Sequence[Concat]

    def to_matcher(self) -> MatchRegex:
        if not self.concats:
            return [True, True, False]
        
        output = [Progress(ProgressIndex(0), RegexIndex(1), RegexIndex(2)), True, False]
        
        rest = self.concats
        while rest:
            current, rest = rest[0].to_matcher(), rest[1:]
            current = combine_two_matchers([Split("|", RegexIndex)])



@dataclass
class Concat(Spanned):
    regexes: Sequence[RegexItem]

    def to_matcher(self) -> MatchRegex:
        if not self.regexes:
            return [True, False]
        
        output, rest = self.regexes[0].to_matcher(), self.regexes[1:]
        while rest:
            next_to_chain, rest = rest[0].to_matcher(), rest[1:]
            output = combine_two_matchers(output, next_to_chain)
        return output

@dataclass
class Group(Spanned):
    contents: Alt

    def to_matcher(self) -> MatchRegex:
        return self.contents.to_matcher()

@dataclass
class Repeat(Spanned):
    repeated: Repeatable

    def to_matcher(self) -> MatchRegex:
        output: MatchRegex = self.repeated.to_matcher()
        return combine_two_matchers(output, second=[Split("+", RegexIndex(-len(output)), RegexIndex(1)), True, False])

@dataclass
class RegexError(Spanned):
    inner: RegexItem | None | Alt
    message: str

    def to_matcher(self) -> MatchRegex:
        return [False, True, False]

type RegexItem = Group | Repeat | RegexLiteral | RegexError
Repeatable = Group | RegexLiteral | RegexError
type Regex = Alt | Concat | RegexItem

def parser(tokens: Sequence[Token]) -> Alt:
    index = 0
    span_index = 0
    group_stack: list[tuple[list[Concat], list[RegexItem], int]] = []
    length = len(tokens)
    concat_storage: list[Concat] = []
    current_concat: list[RegexItem] = []

    def push_current_concat_to_storage() -> None:
        nonlocal concat_storage, current_concat, span_index
        if len(current_concat) > 0:
            concat_storage.append(Concat(current_concat[0].start, current_concat[-1].end, current_concat))
        else:
            concat_storage.append(Concat(span_index, span_index, current_concat))
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
                        current_concat.append(Repeat(for_inspection.start, for_inspection.end + 1, for_inspection))
                    else:
                        current_concat.append(for_inspection)
                        current_concat.append(RegexError(span_index, span_index + 1, None, "Repeat with invalid element to repeat"))
                else:
                    current_concat.append(RegexError(span_index, span_index + 1, None, "Repeat with nothing to repeat"))
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
                    current_concat.append(RegexError(span_index, span_index + 1, None, "Unopened group"))
                    span_index += 1
                else:
                    push_current_concat_to_storage()
                    stored_concat_storage, stored_current_concat, stored_span_index = group_stack.pop()
                    stored_current_concat.append(Group(stored_span_index, span_index + 1, Alt(concat_storage[0].start, concat_storage[-1].end, concat_storage)))
                    concat_storage = stored_concat_storage
                    current_concat = stored_current_concat
                    span_index += 1
        index += 1
    push_current_concat_to_storage()
    while group_stack:
        stored_concat_storage, stored_current_concat, stored_span_index = group_stack.pop()
        stored_current_concat.append(RegexError(stored_span_index, span_index, Alt(concat_storage[0].start, concat_storage[-1].end, concat_storage), "Unclosed group"))
        concat_storage = stored_concat_storage
        current_concat = stored_current_concat
        push_current_concat_to_storage()
    return Alt(concat_storage[0].start, concat_storage[-1].end, concat_storage)

@final
@dataclass
class Split:
    reason: Literal["|", "+"]
    greedy: RegexIndex
    lazy: RegexIndex

@final
@dataclass
class Item:
    char: str
    matches: RegexIndex
    fails: RegexIndex

@final
@dataclass
class Progress:
    index: ProgressIndex
    matches: RegexIndex
    fails: RegexIndex

InputIndex = NewType("InputIndex", int)
RegexIndex = NewType("RegexIndex", int)
ProgressIndex = NewType("ProgressIndex", int)
ProgressTracker = NewType("ProgressTracker", list[None | InputIndex])

type MatchRegex = Sequence[Item | Split | bool | Progress]

def combine_two_matchers(first: MatchRegex, second: MatchRegex) -> MatchRegex:
    new_false_offset = len(second) - 2
    first_len = len(first)
    false_index = first_len - 1
    for item in first:
        match item:
            case bool():
                pass
            case Item() | Progress():
                if item.matches == false_index:
                    item.matches = RegexIndex(item.matches + new_false_offset)
                if item.fails == false_index:
                    item.fails = RegexIndex(item.fails + new_false_offset)
            case Split():
                if item.greedy == false_index:
                    item.greedy = RegexIndex(item.greedy + new_false_offset)
                if item.lazy == false_index:
                    item.lazy = RegexIndex(item.lazy + new_false_offset)
    for item in second:
        match item:
            case bool():
                pass
            case Item() | Progress():
                item.matches = RegexIndex(item.matches + first_len)
                item.fails = RegexIndex(item.fails + first_len)
            case Split():
                item.greedy = RegexIndex(item.greedy + first_len)
                item.lazy = RegexIndex(item.lazy + first_len)
    return [*first[:-2], *second]

def matches(regex: MatchRegex, input: str, regex_index: RegexIndex = RegexIndex(0)) -> bool:  # pyright: ignore[reportCallInDefaultInitializer]
    stack: list[tuple[InputIndex, RegexIndex, ProgressTracker]] = []
    progress_tracker: ProgressTracker = ProgressTracker([None for op in regex if isinstance(op, Progress)])

    progress_index = 0
    for item in regex:
        if isinstance(item, Progress):
            item.index = ProgressIndex(progress_index)
            progress_index += 1

    index = InputIndex(0)

    while True:
        current = regex[regex_index]
        logger.debug(index, regex_index, current, progress_tracker, stack)
        match current:
            case Item():
                regex_index = current.matches if input[index] == current.char else current.fails
            case Progress():
                last_index = progress_tracker[current.index]
                if last_index is None or index > last_index:
                    progress_tracker[current.index] = index
                    regex_index = current.matches
                else:
                    regex_index = current.fails
            case Split():
                stack.append((index, current.lazy, copy(progress_tracker)))
                regex_index = current.greedy
            case False:
                if stack:
                    index, regex_index, progress_tracker = stack.pop()
            case True:
                return True

# print(matches([True, False, Progress(0, 3, 1), Split("|", 4, 5), Item("a", 5, 1), Split("+", 2, 0)], "x", 2))

@final
class Editor(tk.Tk):
    def __init__(self) -> None:
        tk.Tk.__init__(self)
        self.geometry("600x400")
        self.entry_frame = tk.Frame(self)
        text_widget = tk.Text(self.entry_frame)
        text_widget.pack(side="top", anchor="n", expand=False)
        _ = text_widget.bind("<KeyRelease>", self.highlight_text)
        self.entry_frame.pack(side="left", anchor="nw", expand=False)

    def highlight_text(self, event: tk.Event):
        widget = event.widget
        if not isinstance(widget, tk.Text):
            raise TypeError("Tried to highlight non-text widget")

        for tag in widget.tag_names(index=None):
            if tag.startswith("highlight"):
                widget.tag_remove(tag, "1.0", tk.END)

        height = widget.winfo_height()
        area_start = widget.count("1.0", widget.index("@0,0"))
        area_start = area_start[0] if area_start is not None else 0
        area_end = widget.count("1.0", widget.index(f"@0,{height}"))
        area_end = area_end[0] if area_end is not None else 100000000000

        def highlight_text_widget(start: int, end: int, color: str) -> None:
            # For performance, don't make highlights that wouldn't be visible anyways
            if (start < area_start and end < area_end) or (start > area_start and end > area_end):
                return
            # widget.tag_add(f"highlight-{start}-{end}", f"1.0+{start} chars", f"1.0+{end} chars")
            # _ = widget.tag_configure(f"highlight-{start}-{end}", background=color)
            widget.tag_add(f"highlight-{color}", f"1.0+{start} chars", f"1.0+{end} chars")
            _ = widget.tag_configure(f"highlight-{color}", background=color)

        parsed = parser(lexer(widget.get("1.0", tk.END)[:-1]))
        # print(parsed)
        stack: list[RegexItem | Concat | Alt] = [parsed]
        while stack:
            current = stack.pop()
            match current:
                case Group():
                    highlight_text_widget(current.start, current.contents.start, "lightgreen")
                    stack.append(current.contents)
                    highlight_text_widget(current.contents.end, current.end, "lightgreen")
                case Repeat():
                    stack.append(current.repeated)
                    highlight_text_widget(current.repeated.end, current.end, "lightblue")
                case RegexLiteral():
                    pass
                case RegexError():
                    if current.inner is not None:
                        stack.append(current.inner)
                        if current.start != current.inner.start:
                            highlight_text_widget(current.start, current.inner.start, "pale violet red")
                        if current.inner.end != current.end:
                            highlight_text_widget(current.inner.end, current.end, "pale violet red")
                    else:
                        highlight_text_widget(current.start, current.end, "pale violet red")
                case Concat():
                    stack.extend(current.regexes)
                case Alt():
                    stack.extend(current.concats)
                    for index in range(1, len(current.concats)):
                        highlight_text_widget(current.concats[index-1].end, current.concats[index].start, "lightblue")

if __name__ == "__main__":
    if "-v" in sys.argv:
        logging.basicConfig(level=logging.DEBUG)
        sys.argv.remove("-v")
    if len(sys.argv) == 1:
        Editor().mainloop()
    elif len(sys.argv) > 3 and sys.argv[2] == "matches":
        lexed = lexer(sys.argv[1])
        parsed = parser(lexed)
        # breakpoint()
        # match = parsed.matches(sys.argv[3], 0)
        # print([*match])
        print(matches(parsed.to_matcher(), sys.argv[3]))
