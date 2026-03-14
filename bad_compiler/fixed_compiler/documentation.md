# .wut Language — Reverse Engineering & Compiler Fix Documentation

## Overview

`broken_compiler.exe` is a Windows PE32 binary (compiled with GCC/MinGW 6.3.0) that
interprets a custom stack-based programming language stored in `.wut` source files.
The compiler contained two bugs that caused incorrect / crashed output when running
`program.wut`. This document describes the reverse-engineering process, the bugs found,
their fixes, and the custom showcase program written in `.wut`.

---

## Reverse Engineering Methodology

### 1. Binary Identification
```
file broken_compiler.exe
→ PE32 executable (console) Intel 80386 (stripped to external PDB), for MS Windows
```

### 2. String Extraction
Running `strings` on the binary revealed error messages embedded in the interpreter:
- `"Error: stack overflow"`
- `"Error: stack underflow"`
- `"Error: stack empty"`
- `"Error: unmatched *"`
- `"Usage: %s <source file>"`

This confirmed a **stack-based language** with loop constructs (`*` matching).

### 3. PE Section Analysis
The binary has 8 sections. Key sections:

| Section  | VA       | File Offset | Size  |
|----------|----------|-------------|-------|
| `.text`  | 0x1000   | 0x400       | 0x1800|
| `.rdata` | 0x4000   | 0x1E00      | 0x600 |
| `.bss`   | 0x6000   | —           | —     |

### 4. Dispatch Table Discovery

The main interpreter loop at VA `0x402370` reads one byte of source at a time, then:
```asm
movzbl (%eax),%ecx        ; read char
lea    -0x21(%ecx),%edx   ; edx = char - 0x21 ('!')
cmp    $0x5d,%dl          ; if > 93: skip (default/NOP)
ja     0x4023d2
jmp    *0x4040f4(,%edx,4) ; dispatch table indexed by (char - 33)
```

This revealed a **256-entry jump table** at VA `0x4040f4`, indexed by `char - 0x21`.
Every source character in range `'!'` (33) to `'~'` (126) maps to a handler function.

### 5. Handler Mapping

By reading the jump table and disassembling each handler:

| Token | Handler VA | Operation |
|-------|------------|-----------|
| `~`   | 0x402624   | Push 65 (`'A'`) |
| `!`   | 0x4025d0   | Increment top of stack |
| `@`   | 0x4025e2   | Decrement top of stack |
| `%`   | 0x402460   | Pop two, push sum |
| `#`   | 0x402501   | Negate top in-place |
| `$`   | 0x4024b2   | **BUGGY** — see below |
| `^`   | 0x4023a0   | **BUGGY** — see below |
| `` ` ``| 0x4023bd  | Pop and discard |
| `(`   | 0x402540   | Push integer (reads digits) |
| `&`   | 0x402400   | Loop start |
| `*`   | 0x4025f4   | Loop end |

Whitespace and all other characters are silently ignored (fall to default handler).

---

## Bugs Found

### Bug 1 — `$` (DUP): Pushes two extra copies instead of one

**Disassembly of handler at 0x4024b2:**
```asm
mov    0x403004,%eax       ; eax = stack pointer (sp)
mov    0x406080(,%eax,4),%ecx  ; ecx = stack[sp] (top value)
lea    0x1(%eax),%edx
mov    %edx,0x403004       ; sp = sp + 1     ← FIRST write
mov    %ecx,0x406080(,%edx,4)  ; stack[sp+1] = top
add    $0x2,%eax
mov    %eax,0x403004       ; sp = sp + 2     ← SECOND write (overwrites!)
mov    %ecx,0x406080(,%eax,4)  ; stack[sp+2] = top
```

The handler writes `sp+1` to the stack-pointer register, then immediately overwrites it
with `sp+2`, and stores the duplicated value at **both** `sp+1` and `sp+2`. This means
`$` pushes **two** extra copies of the top value (3 total on stack) instead of the
intended one extra copy.

**Correct behaviour:** `$` should be the **OVER** operation — copy the
*second-from-top* value to the top:
```
Before: [A, B]   →   After: [A, B, A]
```

**Effect of bug:** From the 4th character printed onwards, the stack accumulates
garbage values. The 5th computation produces a negative number, crashing with an
invalid `chr()` call.

---

### Bug 2 — `^` (print): Pops after printing, destroying the accumulator

**Disassembly of handler at 0x4023a0:**
```asm
mov    0x403004,%eax           ; load sp
movsbl 0x406080(,%eax,4),%eax ; eax = stack[sp]
call   putchar(eax)            ; print character
; falls through to '`' handler at 0x4023bd:
mov    0x403004,%eax
sub    $0x1,%eax
mov    %eax,0x403004           ; sp-- (POP!)
```

The `^` handler falls through directly into the `` ` `` (pop) handler after calling
`putchar`. This means **every print also pops the value**.

The `.wut` language uses a **running accumulator** encoding: each character's value is
the *previous* character's value plus a small delta. For this to work, the previous
value must remain on the stack after printing.

**Correct behaviour:** `^` should print the top of stack **without popping** it.

**Effect of bug:** After the first character is printed and its value is popped, the
loop counter `(3` has nothing below it. After the loop, `%` tries to pop two values
but only one exists → stack underflow → crash after `"Thi\n"`.

---

## How the Language Works

`.wut` is a stack-based language using a **running-total / delta-encoding** style for
output. The stack maintains an accumulator (the value of the last-printed character),
and each new character is reached by adding a delta to it.

### Loop Semantics
```
(N &  body  *
```
- `(N` — push loop counter N
- `&` — if top ≠ 0: mark loop start; if top = 0: skip to matching `*`
- `*` — if top ≠ 0: jump back to `&`; if top = 0: exit loop (zero stays on stack as neutral element for next `%`)

### Typical character encoding pattern
```
~~%(46#%^    →  65+65-46 = 84 = 'T'
(20%^        →  current + 20 (delta encoding)
~~#%%!^      →  complex arithmetic using 65 as base adjustment
```

### `$` (OVER) use pattern
```
(0$%(10%^
```
This copies the accumulator (second-from-top) over the `0`, then adds `10` to it,
computing `accumulator + 0 + 10 = accumulator + 10`.

---

## Broken vs Fixed Output

| Compiler | Output |
|----------|--------|
| `broken_compiler.exe` | `Thi` + newline, then **crash** (stack underflow) |
| `fixed_compiler.py` | `This is right! Congratulations` |

---

## Custom Showcase Program (`team_showcase.wut`)

```
~~%(42#%^(8#%^(4#%^(3%^(6#%^(11%^(74#%^(73%^(33%^(19#%^(17%^!^(57#%^(26#%^(5&$(10%^`@*`(22#%^
```

### Output
```
XPLOIT
Stars: *****
```

### How it works

**String printing (delta encoding):**
```
~~%(42#%^  →  130 - 42 = 88 = 'X'
(8#%^      →  88 - 8  = 80 = 'P'
(4#%^      →  80 - 4  = 76 = 'L'
(3%^       →  76 + 3  = 79 = 'O'
(6#%^      →  79 - 6  = 73 = 'I'
(11%^      →  73 + 11 = 84 = 'T'
(74#%^     →  84 - 74 = 10 = '\n'
...        →  "Stars: " via further deltas
```

**Loop (prints `*` five times):**
```
(5         push loop counter 5
&          loop start (5 ≠ 0, enter)
  $        OVER: copy accumulator (32 = space) below counter to top
  (10%     add 10 → 42 = '*'
  ^        print '*' (no pop)
  `        discard 42 (restore stack to [acc, counter])
  @        decrement counter
*          loop end (jump back if counter ≠ 0)
`          discard leftover 0
(22#%^     print '\n' (32 - 22 = 10)
```

This demonstrates:
- **Loop construct** (`&` … `*`) with a counted loop
- **OVER** (`$`) to access the accumulator from inside a loop
- **Delta arithmetic** (`#`, `%`, `!`, `@`) for compact character computation
- **Stack discipline** (using `` ` `` to restore stack after printing inside a loop)

---

## Files Delivered

| File | Description |
|------|-------------|
| `fixed_compiler.py` | Fixed Python interpreter for `.wut` programs |
| `program.wut` | Original program (unchanged) — now runs correctly |
| `team_showcase.wut` | Custom `.wut` program demonstrating language features |
| `documentation.md` | This document |
