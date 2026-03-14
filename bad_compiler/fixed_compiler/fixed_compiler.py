#!/usr/bin/env python3
"""
Fixed .wut Language Compiler/Interpreter
=========================================
Usage: python fixed_compiler.py <source.wut>

Language Specification:
  ~   Push 65 ('A') onto the stack
  !   Increment top of stack
  @   Decrement top of stack
  %   Pop top two values, push their sum
  #   Negate top of stack in-place
  $   OVER — copy second-from-top to top  [FIXED]
  ^   Print top of stack as ASCII char     [FIXED — no pop]
  `   Pop and discard top of stack
  (N  Push integer N (N = decimal digits following '(')
  &   Loop start: if top != 0 save position, else skip to matching '*'
  *   Loop end:   if top != 0 jump back to '&', else continue

Bugs Fixed in broken_compiler.exe:
  Bug 1 – '$' (DUP) pushed TWO extra copies (3 total) instead of one extra.
           The correct behaviour is OVER: copy second-from-top to top.
           Impact: corrupted the stack from the 4th character onwards,
           causing a crash mid-way through printing the message.

  Bug 2 – '^' (print) popped the printed value off the stack.
           The correct behaviour is to print WITHOUT popping, so that the
           running accumulator value is preserved for subsequent arithmetic.
           Impact: every character destroyed the accumulator, making
           relative-delta encoding of the next character impossible.
"""

import sys


def run(source: str) -> None:
    stack: list[int] = []
    loop_stack: list[int] = []   # saved instruction-pointer values for '&'
    ip = 0

    while ip < len(source):
        c = source[ip]

        # ── Push integer ───────────────────────────────────────────────
        if c == '(':
            ip += 1
            num_str = ''
            while ip < len(source) and source[ip].isdigit():
                num_str += source[ip]
                ip += 1
            stack.append(int(num_str) if num_str else 0)
            continue

        # ── Push 65 ('A') ──────────────────────────────────────────────
        elif c == '~':
            stack.append(65)

        # ── Increment top ──────────────────────────────────────────────
        elif c == '!':
            if not stack:
                sys.exit("Error: stack empty")
            stack[-1] += 1

        # ── Decrement top ──────────────────────────────────────────────
        elif c == '@':
            if not stack:
                sys.exit("Error: stack empty")
            stack[-1] -= 1

        # ── Add top two, push result ────────────────────────────────────
        elif c == '%':
            if len(stack) < 2:
                sys.exit("Error: stack underflow")
            b = stack.pop()
            a = stack.pop()
            stack.append(a + b)

        # ── Negate top in-place ─────────────────────────────────────────
        elif c == '#':
            if not stack:
                sys.exit("Error: stack empty")
            stack[-1] = -stack[-1]

        # ── OVER: copy second-from-top to top  [FIXED] ──────────────────
        elif c == '$':
            if len(stack) < 2:
                sys.exit("Error: stack underflow")
            stack.append(stack[-2])   # was: stack.append(top); stack.append(top)

        # ── Print top as ASCII char, NO POP  [FIXED] ────────────────────
        elif c == '^':
            if not stack:
                sys.exit("Error: stack empty")
            print(chr(stack[-1]), end='')   # was: print(chr(stack.pop()), end='')

        # ── Pop and discard top ─────────────────────────────────────────
        elif c == '`':
            if not stack:
                sys.exit("Error: stack empty")
            stack.pop()

        # ── Loop start ──────────────────────────────────────────────────
        elif c == '&':
            if not stack:
                sys.exit("Error: stack empty")
            if stack[-1] != 0:
                if not loop_stack or loop_stack[-1] != ip:
                    loop_stack.append(ip)
                # else: re-entered via '*', already tracked — just continue
            else:
                # Skip forward to the matching '*' (handles nesting)
                depth = 1
                ip += 1
                while ip < len(source) and depth > 0:
                    if source[ip] == '&':
                        depth += 1
                    elif source[ip] == '*':
                        depth -= 1
                    ip += 1
                continue  # ip already past the '*'

        # ── Loop end ────────────────────────────────────────────────────
        elif c == '*':
            if not stack:
                sys.exit("Error: stack empty")
            if stack[-1] != 0:
                if not loop_stack:
                    sys.exit("Error: unmatched *")
                ip = loop_stack[-1]   # jump back to '&'
            else:
                # Exit loop; leave 0 on stack (used by next '%' as neutral element)
                if loop_stack:
                    loop_stack.pop()

        # All other characters (whitespace, newlines, …) are ignored
        ip += 1

    print()   # trailing newline after program output


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <source file>")
        sys.exit(1)

    filename = sys.argv[1]
    try:
        with open(filename, 'r') as f:
            source = f.read()
    except OSError:
        print(f"Error: cannot open file '{filename}'")
        sys.exit(1)

    run(source)


if __name__ == '__main__':
    main()
