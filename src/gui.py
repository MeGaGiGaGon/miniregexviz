"""
A basic tkinter gui, currently supports simple syntax highlighting on an input regex.
"""

import tkinter as tk
from typing import final

from src.lexer_parser import to_regex_ast
from src.regex_ast import (
    Alt,
    Concat,
    Group,
    RegexError,
    RegexItem,
    RegexLiteral,
    Repeat,
)


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
            raise TypeError("Tried to highlight non-text widget")

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
            widget.tag_add(f"highlight-{color}", f"1.0+{start} chars", f"1.0+{end} chars")
            _ = widget.tag_configure(f"highlight-{color}", background=color)

        parsed = to_regex_ast(widget.get("1.0", tk.END)[:-1])

        stack: list[RegexItem | Concat | Alt] = [parsed]
        while stack:
            current = stack.pop()
            match current:
                case Group():
                    highlight_text_widget(current.start, current.contents.start, "lightgreen")
                    stack.extend(current.contents.concats)
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
