from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pprint import pp  # pyright: ignore[reportUnusedImport]
import sys
from time import perf_counter
import tkinter as tk
from typing import final, override

class Debug:
    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({", ".join(f"{k}={v}" for k, v in self.__dict__.items())})"  # pyright: ignore[reportAny]

debug_depth = 0
def debug[T, **P](callable: Callable[P, T]) -> Callable[P, T]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> T:
        global debug_depth
        print(f"{"  "*debug_depth}Calling {repr(callable).split(" at")[0][10:]} with ({", ".join(str(x) for x in args)}) {kwargs=}")
        debug_depth += 1
        result = callable(*args, **kwargs)
        debug_depth -= 1
        print(f"{"  "*debug_depth}{result=}")
        return result
    return inner

@dataclass
class Spanned:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start
    
    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}-{self.start}-{self.end}"

@dataclass
class RegexLiteral(Spanned):
    char: str

    @debug
    def matches(self, input: str, index: int) -> tuple[bool, int]:
        if index < len(input) and input[index] == self.char:
            return True, index + 1
        else:
            return False, index

@dataclass
class CharSet(Spanned):
    chars: str

    @debug
    def matches(self, input: str, index: int) -> tuple[bool, int]:
        if index < len(input) and input[index] in self.chars:
            return True, index + 1
        else:
            return False, index

class TokenGroupStart(Debug): ...
class TokenGroupEnd(Debug): ...
class TokenAltSep(Debug): ...
class TokenPlus(Debug): ...

type Token = TokenGroupStart | TokenGroupEnd | TokenAltSep | RegexLiteral | TokenPlus | RegexError | CharSet

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
        elif char == "[":
            starting_index = index
            index += 1
            while index < length:
                if input[index] == "]":
                    break
                index += 1
            else:
                output.append(RegexError(starting_index, index, CharSet(starting_index, index, input[starting_index+1:]), "Unclosed charset"))
                break
            output.append(CharSet(starting_index, index+1, input[starting_index+1:index]))
        else:
            output.append(RegexLiteral(index, index + 1, input[index]))
        index += 1
    return output

@dataclass
class Alt(Spanned):
    concats: Sequence[Concat]

    @debug
    def matches(self, input: str, index: int, starting_concat: int = 0) -> tuple[bool, int, int]:
        for concat_index in range(starting_concat, len(self.concats)):
            matches, new_index = self.concats[concat_index].matches(input, index)
            if matches:
                return True, new_index, concat_index
        return False, index, 0

@dataclass
class Concat(Spanned):
    regexes: Sequence[RegexItem]

    def regexes_to_with_info(self) -> list[tuple[RegexLiteral | CharSet, int | None] | tuple[Group | Repeat, int | None, int | None] | tuple[RegexError]]:
        output: list[tuple[RegexLiteral | CharSet, int | None] | tuple[Group | Repeat, int | None, int | None] | tuple[RegexError]] = []
        for regex in self.regexes:
            match regex:
                case RegexLiteral() | CharSet():
                    output.append((regex, None))
                case Group() | Repeat():
                    output.append((regex, None, None))
                case RegexError():
                    output.append((regex,))
        return output

    @debug
    def matches(self, input: str, index: int) -> tuple[bool, int]:
        regex_with_info = self.regexes_to_with_info()

        regex_index = 0
        length = len(regex_with_info)

        while regex_index < length:
            # pp(regex_with_info)
            # print(index, regex_index)
            if regex_index < 0:
                return False, index

            backtracking_info = regex_with_info[regex_index]
            # print(backtracking_info[0].__class__.__name__, backtracking_info[0].start, backtracking_info[0].end, backtracking_info[1:])
            match backtracking_info:
                case (RegexLiteral() | CharSet() as regex, backtracking_index):
                    matches, new_index = regex.matches(input, index if backtracking_index is None else backtracking_index)
                    if matches:
                        regex_with_info[regex_index] = (regex, index)
                        index = new_index
                        regex_index += 1
                    else:
                        regex_with_info[regex_index] = (regex, None)
                        if backtracking_index is not None:
                            index = backtracking_index
                        regex_index -= 1
                case (Group() | Repeat() as regex, backtracking_index, limit):
                    if isinstance(regex, Group) and limit is None:
                        limit = 0
                    # print(regex_index, index if backtracking_index is None else backtracking_index)
                    matches, new_index, new_limit = regex.matches(input, index if backtracking_index is None else backtracking_index, limit)  # pyright: ignore[reportArgumentType]
                    # print(matches, new_index, new_limit)
                    if matches:
                        regex_with_info[regex_index] = (regex, index, new_limit - 1)
                        index = new_index
                        regex_index += 1
                    else:
                        regex_with_info[regex_index] = (regex, None, None)
                        if backtracking_index is not None:
                            index = backtracking_index
                        regex_index -= 1
                case (RegexError(),):
                    regex_index -= 1
        return True, index

@dataclass
class Group(Spanned):
    contents: Alt

    @debug
    def matches(self, input: str, index: int, starting_concat: int = 0) -> tuple[bool, int, int]:
        return self.contents.matches(input, index, starting_concat)

@dataclass
class Repeat(Spanned):
    repeated: Repeatable

    @debug
    def matches(self, input: str, index: int, repeat_limit: int | None) -> tuple[bool, int, int]:
        repeat_count = 0

        if repeat_limit is None:
            repeat_limit = 1000000000

        while repeat_count < repeat_limit:
            matches = self.repeated.matches(input, index)
            if matches[0]:
                repeat_count += 1
                index = matches[1]
            else:
                break
        if repeat_count >= 1:
            return True, index, repeat_count
        else:
            return False, index, 0

@dataclass
class RegexError(Spanned):
    inner: RegexItem | None | Alt
    message: str

    @debug
    def matches(self, _input: str, index: int) -> tuple[bool, int]:
        return False, index

Repeatable = Group | RegexLiteral | RegexError | CharSet
type RegexItem = Repeat | Repeatable
type Regex = Alt | Concat | RegexItem

def parser(tokens: Sequence[Token]) -> Alt:
    index = 0
    span_index = 0
    group_stack: list[tuple[list[Concat], list[RegexItem], int]] = []
    length = len(tokens)
    concat_storage: list[Concat] = []
    current_concat: list[RegexItem] = []
    def push_current_concat_to_storage():
        nonlocal concat_storage, current_concat, span_index
        if len(current_concat) > 0:
            concat_storage.append(Concat(current_concat[0].start, current_concat[-1].end, current_concat))
        else:
            concat_storage.append(Concat(span_index, span_index, current_concat))
        current_concat = []

    while index < length:
        match tokens[index]:
            case RegexLiteral() | CharSet() | RegexError() as regex:
                current_concat.append(regex)
                span_index += regex.length
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

@dataclass
class MatchInfo:
    regex: Regex
    start: int
    end: int
    child_matches: list[MatchInfo]

    @property
    def length(self) -> int:
        return self.end - self.start
    
    # def backtrack(self):
                                                                                                                                                                                                                     

# def matches(regex: Alt, input: str, index: int) -> bool:
#     group_stack: list[tuple[list[Concat], list[RegexItem], int]] = []
#     concat_storage: list[Concat] = []
#     current_concat: list[RegexItem] = []
#     length = len(input)

#     while True:
#         match regex:
#             case Alt():

@final
class Editor(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.geometry("600x400")
        self.entry_frame = tk.Frame(self)
        text_widget = tk.Text(self.entry_frame)
        text_widget.pack(side="top", anchor="n", expand=False)
        _ = text_widget.bind("<KeyRelease>", lambda e: self.highlight_text(e))
        self.entry_frame.pack(side="left", anchor="nw", expand=False)

    def highlight_text(self, event: tk.Event):
        widget = event.widget
        if not isinstance(widget, tk.Text):
            raise RuntimeError("Tried to highlight non-text widget")

        for tag in widget.tag_names(index=None):
            if tag.startswith("highlight"):
                widget.tag_remove(tag, "1.0", tk.END)

        height = widget.winfo_height()
        area_start = widget.count("1.0", widget.index("@0,0"))
        area_start = area_start[0] if area_start is not None else 0
        area_end = widget.count("1.0", widget.index(f"@0,{height}"))
        area_end = area_end[0] if area_end is not None else 100000000000
        
        def highlight_text_widget(start: int, end: int, color: str):
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
                case CharSet():
                    highlight_text_widget(current.start, current.end, "orange")
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
    if len(sys.argv) == 1:
        Editor().mainloop()
    if sys.argv[1] == "time":
        if sys.argv[2] == "eval":
            inp = str(eval(sys.argv[3]))  # pyright: ignore[reportAny]
        else:
            inp = sys.argv[2]
        start = perf_counter()
        lexed = lexer(inp)
        end_lexing = perf_counter()
        print(f"Lexing took {end_lexing - start}")
        _ = parser(lexed)
        print(f"Parsing took {perf_counter() - end_lexing}")
    else:
        lexed = lexer(sys.argv[1])
        print(lexed)
        parsed = parser(lexed)
        print(parsed)
        if len(sys.argv) > 3 and sys.argv[2] == "matches":
            if len(sys.argv) > 4 and sys.argv[4] == "debug":
                breakpoint()
            print(parsed.matches(sys.argv[3], 0, 0))
        
