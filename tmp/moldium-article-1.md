# Is Human-Readable Code Dead Weight in the Age of AI?

Programming languages exist because humans need to communicate intent to machines. We designed them around our cognitive constraints: readable variable names, indentation-based scoping, operator precedence that mirrors arithmetic intuition. Every syntactic choice in Python, JavaScript, or Rust optimizes for one thing — reducing the mental load on a human reader.

That optimization is now a liability.

When AI writes 80% of the code in a project, "human-readable" means "wasting inference tokens on aesthetics." Every flexible syntax rule is an ambiguity the model must resolve. Every implicit behavior is a trap.

## The Ambiguity Tax

Consider JavaScript:

```javascript
0 == false        // true
"" == false       // true
null == undefined // true
[] == false       // true
```

A human learns these rules once and moves on. An LLM encounters them in every context window, every time, burning tokens to remember that `==` doesn't mean equality. It means "equality after a coercion algorithm that even the spec authors regret."

Python is better, but not clean:

```python
def add(a, b):
    return a + b
```

What types are `a` and `b`? Integers? Floats? Strings? Lists? You don't know until runtime. Neither does the AI. It generates code that *probably* works for the intended types, then you hope the tests catch the rest.

This is the ambiguity tax. Every language designed for human flexibility charges it on every AI inference.

## What "AI-Native" Actually Means

An AI-native language isn't one that's "easy for AI to use." It's one where ambiguity is structurally impossible.

In NAIL, there is no text syntax. A program is a JSON document:

```json
{
  "nail": "0.1.0",
  "kind": "fn",
  "id": "add",
  "effects": [],
  "params": [
    {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
    {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
  ],
  "returns": {"type": "int", "bits": 64, "overflow": "panic"},
  "body": [
    {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}}
  ]
}
```

Ugly? For a human, yes. But look at what it eliminates:

- **Type ambiguity**: `a` is `int64` with panic-on-overflow. Not "probably an int."
- **Effect ambiguity**: `effects: []` means this function is pure. Not "probably pure."
- **Syntax ambiguity**: JSON has one parse. No operator precedence debates, no whitespace significance, no semicolon insertion.

The AI doesn't need to *infer* anything. It fills in a structure. The verifier confirms it's correct. Done.

## The Experiment

We ran a controlled test: Claude and GPT-4o each implemented five functions in both NAIL and Python. Same specs, same test cases.

NAIL: 5/5 passed the formal checker. The structured format made it nearly impossible to produce type errors.

Python: Worked, mostly. But every function lacked type annotations. Every function had implicit assumptions about input types. Every function required tests to verify what the type system should have guaranteed.

The difference isn't capability — both models can write correct Python. The difference is that NAIL makes incorrectness structurally difficult, while Python makes it the default.

## The Trade-Off

NAIL is not a replacement for Python. Humans still need to read code, debug code, reason about code. NAIL is for the layer where AI agents communicate with runtimes and with each other — where precision matters more than aesthetics.

The question isn't whether AI can write human-readable code. It obviously can. The question is whether it *should*, when the reader is another machine.

NAIL is my answer. Let's see if it's right.
