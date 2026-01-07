"""
A basic tkinter gui, currently supports simple syntax highlighting on an input regex.
"""

import tkinter as tk
from typing import final

from src.lexer_parser import parse
from src.regex_ast import (
    EOF,
    Alt,
    AltEnd,
    GroupEnd,
    GroupStart,
    RegexError,
    RegexLiteral,
    RepeatEnd,
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

        parsed = parse(widget.get("1.0", tk.END)[:-1])

        for current in parsed:
            match current:
                case GroupStart() | GroupEnd():
                    highlight_text_widget(current.start, current.start + 1, "lightgreen")
                case RepeatEnd():
                    highlight_text_widget(current.end - 1, current.end, "lightblue")
                case RegexLiteral() | AltEnd() | EOF():
                    pass
                case RegexError():
                    highlight_text_widget(current.start, current.end, "pale violet red")
                case Alt(option_indexes=option_indexes):
                    for index in option_indexes:
                        highlight_text_widget(parsed[index].start - 1, parsed[index].start, "lightblue")
