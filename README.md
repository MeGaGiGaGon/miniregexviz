# MiniRegexViz

A basic implementation of tooling for a super minimal regex language.

## Installation

This project uses uv. If you do not have it installed, see:
https://docs.astral.sh/uv/#installation

```powershell
PS > git clone https://github.com/MeGaGiGaGon/miniregexviz.git  # Clone the project from git
PS > cd miniregexviz  # Move into the new folder
PS miniregexviz> uv run main.py  # Run the GUI
```

```
Usage:
main.py: run gui
main.py help: Show this message
main.py parse "regex": print parsed result of "regex"
main.py match "regex" "data" start?: print where the index regex matches data till, starting at start
main.py scan "regex" "data" start?: print where the index regex matches data till, scanning from start

Add --pdb to drop into debugger on run
```

## MiniRegex Specification

`|`: Adds a new alternation to the current scope. `a|b` will first try to match `a`, and then `b` if `a` fails.
`(` and `)`: Makes a new group. The enclosed contents are a new scope, that is a seperate from the outer one the group is part of. Matches if the contents match.
`+`: Greedily repeats the targeted item. Requires the target to match at least once. Valid repeat targets are literals and groups.
Any other character is treated as a literal, that matches if the character at the current index being matched equals it.

## GUI Info

The top left panel is for inputing the regex.
The top right panel shows the AST for that regex.
The bottom right panel is for inputing text to match against.
The bottom left panel shows the matching debug output.

## Why

The eventual goal is to implement even more features over Python's regex variant, but that is very large in scope. This project exists to implement a much simpler version that should still share the same core implementation problems to prove the methods used are viable. 
