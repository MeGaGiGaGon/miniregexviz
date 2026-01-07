"""
A basic tkinter gui, currently supports simple syntax highlighting on an input regex.
"""

import dataclasses
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
        _ = self.entry_frame.grid_columnconfigure(1, weight=1)

        self.regex_place = tk.Text(self.entry_frame)
        self.regex_place.grid(column=0, row=0, sticky="NSEW")
        _ = self.regex_place.bind("<KeyRelease>", self.highlight_text)
        _ = self.regex_place.bind("<MouseWheel>", self.highlight_text)

        self.matches_place = tk.Text(self.entry_frame)
        self.matches_place.grid(column=0, row=1, sticky="NSEW")
        _ = self.matches_place.bind("<KeyRelease>", self.update_matches)
        _ = self.matches_place.bind("<MouseWheel>", self.update_matches)

        self.ast_display = tk.Text(self.entry_frame)
        self.ast_display.grid(column=1, row=0, sticky="NSEW")
        _ = self.ast_display.configure(state="disabled")

        self.match_debug = tk.Text(self.entry_frame)
        self.match_debug.grid(column=1, row=1, sticky="NSEW")
        _ = self.match_debug.configure(state="disabled")

        self.entry_frame.pack(side="left", anchor="nw", expand=False)
        self.regex_text = ""
        self.parsed = parse(self.regex_text)
        self.matches_text = ""

        self.highlight_text()  # Run highlight so that the ast and match outputs are not empty

    def highlight_text(self, _event: tk.Event | None = None):
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

        _ = self.ast_display.configure(state="normal")
        ast_text: list[str] = []
        for re_index, re in enumerate(self.parsed):
            ast_text.append(f"{re_index} {re.__class__.__name__}({", ".join(f"{k}={v}" for k, v in dataclasses.asdict(re).items() if k != "source")})")  # pyright: ignore[reportAny]
        _ = self.ast_display.delete("1.0", tk.END)
        self.ast_display.insert("1.0", "\n".join(ast_text))
        _ = self.ast_display.configure(state="disabled")


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

    def update_matches(self, _event: tk.Event | None = None):
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

        def remove_highlight_text_widget(start: int, end: int, color: str):
            # For performance, don't remove highlights that wouldn't be visible anyways
            if (start < area_start and end < area_end) or (start > area_start and end > area_end):
                return
            widget.tag_remove(f"highlight-{color}", f"1.0+{start} chars", f"1.0+{end} chars")

        starting_index = 0
        self.matches_text = widget.get("1.0", tk.END)[:-1]

        blue_colors= ["SteelBlue1", "DodgerBlue2"]
        green_colors= ["OliveDrab2", "chartreuse3"]
        blue_color = 0
        green_color = 0
        debug_output: list[str] = []

        while True:
            result, scan_debug = scan(self.parsed, self.matches_text, starting_index)
            debug_output.extend(scan_debug)
            if result is None:
                break
            match result:
                case [(match_start, new_start), *_]:
                    if new_start > starting_index:
                        starting_index = new_start
                    else:
                        starting_index += 1
                    highlight_text_widget(match_start, new_start, blue_colors[blue_color])
                    blue_color = not blue_color
                case _:
                    raise RuntimeError("Internal Error: Scan did not give a tuple as first result")

            for group in result[1:]:
                if isinstance(group, tuple):
                    highlight_text_widget(group[0], group[1], green_colors[green_color])
                    green_color = not green_color
                    for color in blue_colors:
                        remove_highlight_text_widget(group[0], group[1], color)

        if not debug_output:
            debug_output = ["No text to match against"]

        _ = self.match_debug.configure(state="normal")
        _ = self.match_debug.delete("1.0", tk.END)
        self.match_debug.insert("1.0", "\n".join(debug_output))
        _ = self.match_debug.configure(state="disabled")
