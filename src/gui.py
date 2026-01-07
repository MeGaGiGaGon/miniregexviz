"""
A basic tkinter gui, currently supports simple syntax highlighting on an input regex.
"""

import tkinter as tk
from typing import final

from src.lexer_parser import parse
from src.matcher import scan
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
        _ = self.entry_frame.grid_rowconfigure(0, weight=1)
        _ = self.entry_frame.grid_rowconfigure(1, weight=1)
        _ = self.entry_frame.grid_columnconfigure(0, weight=1)
        self.regex_place = tk.Text(self.entry_frame)
        self.regex_place.grid(column=0, row=0, sticky="NSEW")
        _ = self.regex_place.bind("<KeyRelease>", self.highlight_text)
        _ = self.regex_place.bind("<MouseWheel>", self.highlight_text)
        self.matches_place = tk.Text(self.entry_frame)
        self.matches_place.grid(column=0, row=1, sticky="NSEW")
        _ = self.matches_place.bind("<KeyRelease>", self.update_matches)
        _ = self.matches_place.bind("<MouseWheel>", self.update_matches)
        self.entry_frame.pack(side="left", anchor="nw", expand=False)
        self.regex_text = ""
        self.parsed = parse(self.regex_text)
        self.matches_text = ""

    def highlight_text(self, _: tk.Event | None = None):
        widget = self.regex_place

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

        self.regex_text = self.regex_place.get("1.0", tk.END)[:-1]
        self.parsed = parse(self.regex_text)

        for current in self.parsed:
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
                        highlight_text_widget(self.parsed[index].start - 1, self.parsed[index].start, "lightblue")

        self.update_matches()

    def update_matches(self, _: tk.Event | None = None):
        widget = self.matches_place

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

        starting_index = 0
        self.matches_text = widget.get("1.0", tk.END)[:-1]
        colors= ["SteelBlue1", "DodgerBlue2"]
        color = 1

        while True:
            result = scan(self.parsed, self.matches_text, starting_index)
            if result is None:
                break
            highlight_text_widget(result[0], result[1], colors[color])
            starting_index = result[1]
            color = not color
