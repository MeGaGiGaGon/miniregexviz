"""
Usage:
uv run main.py: run gui
uv run main.py help: Show this message
uv run main.py parse "regex": print parsed result of "regex"
uv run main.py match "regex" "data" start?: print where the index regex matches data till, starting at start
uv run main.py scan "regex" "data" start?: print where the index regex matches data till, scanning from start

Add --pdb to drop into debugger on run
"""

import sys

from src.gui import Editor
from src.lexer_parser import parse
from src.matcher import matches, scan


def main():
    Editor().mainloop()


if __name__ == "__main__":
    args = sys.argv
    if args and args[0].endswith("main.py"):
        args = args[1:]

    if "--pdb" in args:
        args.remove("--pdb")
        breakpoint()

    match args:
        case []:
            main()
        case ["parse", regex_source]:
            for index, regex in enumerate(parse(regex_source)):
                print(index, regex)
        case ["match", regex_source, target, *rest] if (len(rest) == 1 and (start:=int(rest[0]))) or len(rest) == (start:=0):
            print(matches(parse(regex_source), target, start))
        case ["scan", regex_source, target, *rest] if (len(rest) == 1 and (start:=int(rest[0]))) or len(rest) == (start:=0):
            print(scan(parse(regex_source), target, start))
        case _:
            print(__doc__)
