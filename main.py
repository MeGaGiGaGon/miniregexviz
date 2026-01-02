from collections.abc import Sequence
from dataclasses import dataclass
import logging
from pprint import pp  # pyright: ignore[reportUnusedImport]
import sys
import tkinter as tk
from typing import final, override

logger = logging.getLogger()
_old_debug = logger.debug
def _new_debug(*inputs: object):
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

    def matches(self, input: str, index: int) -> list[int]:
        global indent
        if index < len(input) and input[index] == self.char:
            logger.debug("| "* indent, self, index, input[index], index + 1)
            return [index + 1]
        logger.debug("| "* indent, self, index, "BACKTRACK")
        return []

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

    def matches(self, input: str, index: int) -> list[int]:
        global indent
        logger.debug("| "* indent, "Alt", self.start, self.end, index)
        indent += 1
        result = [inner_index for concat in self.concats for inner_index in concat.matches(input, index)]
        indent -= 1
        logger.debug("| "* indent, "->Alt", self.start, self.end, result)
        return result

@dataclass
class Concat(Spanned):
    regexes: Sequence[RegexItem]

    def matches(self, input: str, index: int) -> list[int]:
        global indent
        logger.debug("| "* indent, "Con", self.start, self.end, index)
        indent += 1
        if not self.regexes:
            return list[int]()

        length = len(self.regexes)
        res = self.regexes[0].matches(input, index)
        backtracking_storage: list[list[int]] = [res]
        logger.debug("| "* indent, "add to storage", res)
        indent += 1
        
        result: list[int] = []
        while backtracking_storage:
            if len(backtracking_storage) >= length:
                res = backtracking_storage.pop()
                result.extend(res)
                indent -= 1
                logger.debug("| "* indent, "add to result", res)
            elif backtracking_storage[-1]:
                next_index = backtracking_storage[-1].pop(0)
                logger.debug("| "* indent, "pop last storage", backtracking_storage[-1], next_index)
                indent += 1
                res = self.regexes[len(backtracking_storage)].matches(input, next_index)
                backtracking_storage.append(res)
                logger.debug("| "* indent, "add to storage", res)
            else:
                indent -= 1
                logger.debug("| "* indent, "storage empty")
                _ = backtracking_storage.pop()
        indent -= 1
        logger.debug("| "* indent, "->Con", self.start, self.end, result)
        return result

@dataclass
class Group(Spanned):
    contents: Alt

    def matches(self, input: str, index: int) -> list[int]:
        global indent
        logger.debug("| "* indent, "Group", self.start, self.end, index)
        indent += 1
        result = self.contents.matches(input, index)
        indent -= 1
        logger.debug("| "* indent, "->Group", self.start, self.end, result)
        return result

@dataclass
class Repeat(Spanned):
    repeated: Repeatable

    def matches(self, input: str, index: int) -> list[int]:
        global indent
        logger.debug("| "* indent, "Repeat", self.start, self.end, index)
        indent += 1

        output: list[list[int]] = []
        for index in self.repeated.matches(input, index):
            output.append([index])
            output.append(self.matches(input, index))

        indent -= 1
        logger.debug("| "* indent, "->Repeat", self.start, self.end, output[::-1])
        return [inner for nested in output[::-1] for inner in nested]

        # global indent
        # logger.debug("| "* indent, "Repeat", self.start, self.end, index)
        # indent += 1

        # res = self.repeated.matches(input, index)
        # backtracking_storage: list[list[int]] = [res]
        # logger.debug("| "* indent, "rres add", res)
        # indent += 1

        # result: list[list[int]] = [res[::]]

        # while backtracking_storage:
        #     if backtracking_storage[-1]:
        #         next_index = backtracking_storage[-1].pop(0)
        #         logger.debug("| "* indent, "rmatching at", next_index)
        #         logger.debug("| "* indent, "pop last rstorage", backtracking_storage[-1], next_index)
        #         indent += 1
        #         res = self.repeated.matches(input, next_index)
        #         result.append(res[::])
        #         logger.debug("| "* indent, "rres add", res)
        #         backtracking_storage.append(res)
        #     else:
        #         indent -= 1
        #         logger.debug("| "* indent, "rstorage empty")
        #         _ = backtracking_storage.pop()
        # indent -= 1
        # logger.debug("| "* indent, "->Repeat", self.start, self.end, result[::-1])
        # return [inner for nested in result[::-1] for inner in nested]

@dataclass
class RegexError(Spanned):
    inner: RegexItem | None | Alt
    message: str

    def matches(self, _input: str, _index: int) -> list[int]:
        return []

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

    def push_current_concat_to_storage():
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
        match = parsed.matches(sys.argv[3], 0)
        print([*match])
