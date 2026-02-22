"""
Phase 2 Experiment — Python Implementations
Same specs as the NAIL programs. Written by LLM without type constraints.
"""

# P1: is_even
def is_even(n):
    return n % 2 == 0

# P2: abs_val
def abs_val(n):
    if n < 0:
        return -n
    return n

# P3: max_of_two
def max_of_two(a, b):
    if a >= b:
        return a
    return b

# P4: clamp
def clamp(val, lo, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val

# P5: factorial
def factorial(n):
    acc = 1
    for i in range(1, n + 1):
        acc *= i
    return acc
