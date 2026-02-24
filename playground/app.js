// NAIL Playground — Frontend Logic

const API_URL = "http://127.0.0.1:7429/run";

// ── Example Programs ────────────────────────────────────────────────────────

const EXAMPLES = {
  hello: {
    label: "Hello, NAIL",
    description: "Prints a greeting. No arguments.",
    args: {},
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "main",
      "effects": ["IO"],
      "params": [],
      "returns": { "type": "unit" },
      "body": [
        { "op": "print", "val": { "lit": "Hello, NAIL" }, "effect": "IO" },
        { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
      ]
    }
  },

  fibonacci: {
    label: "Fibonacci(n)",
    description: "Computes the Nth Fibonacci number. Pass arg n (e.g. 10).",
    args: { n: 10 },
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "fibonacci",
      "effects": [],
      "params": [
        { "id": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" } }
      ],
      "returns": { "type": "int", "bits": 64, "overflow": "panic" },
      "body": [
        { "op": "let", "id": "a", "type": { "type": "int", "bits": 64, "overflow": "panic" }, "val": { "lit": 0 }, "mut": true },
        { "op": "let", "id": "b", "type": { "type": "int", "bits": 64, "overflow": "panic" }, "val": { "lit": 1 }, "mut": true },
        { "op": "let", "id": "tmp", "type": { "type": "int", "bits": 64, "overflow": "panic" }, "val": { "lit": 0 }, "mut": true },
        {
          "op": "loop",
          "bind": "i",
          "from": { "lit": 0 },
          "to": { "ref": "n" },
          "step": { "lit": 1 },
          "body": [
            { "op": "assign", "id": "tmp", "val": { "op": "+", "l": { "ref": "a" }, "r": { "ref": "b" } } },
            { "op": "assign", "id": "a", "val": { "ref": "b" } },
            { "op": "assign", "id": "b", "val": { "ref": "tmp" } }
          ]
        },
        { "op": "return", "val": { "ref": "a" } }
      ]
    }
  },

  factorial: {
    label: "Factorial(n)",
    description: "Computes n! iteratively. Pass arg n (e.g. 10).",
    args: { n: 10 },
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "factorial",
      "effects": [],
      "params": [
        { "id": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" } }
      ],
      "returns": { "type": "int", "bits": 64, "overflow": "panic" },
      "body": [
        { "op": "let", "id": "result", "type": { "type": "int", "bits": 64, "overflow": "panic" }, "val": { "lit": 1 }, "mut": true },
        {
          "op": "loop",
          "bind": "i",
          "from": { "lit": 1 },
          "to": { "op": "+", "l": { "ref": "n" }, "r": { "lit": 1 } },
          "step": { "lit": 1 },
          "body": [
            { "op": "assign", "id": "result", "val": { "op": "*", "l": { "ref": "result" }, "r": { "ref": "i" } } }
          ]
        },
        { "op": "return", "val": { "ref": "result" } }
      ]
    }
  },

  countdown: {
    label: "Countdown",
    description: "Counts down from 5 to 1, then prints Liftoff!",
    args: {},
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "main",
      "effects": ["IO"],
      "params": [],
      "returns": { "type": "unit" },
      "body": [
        { "op": "let", "id": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" }, "val": { "lit": 5 } },
        {
          "op": "loop",
          "bind": "i",
          "from": { "lit": 0 },
          "to": { "lit": 5 },
          "step": { "lit": 1 },
          "body": [
            {
              "op": "print",
              "val": { "op": "int_to_str", "v": { "op": "-", "l": { "ref": "n" }, "r": { "ref": "i" } } },
              "effect": "IO"
            }
          ]
        },
        { "op": "print", "val": { "lit": "Liftoff!" }, "effect": "IO" },
        { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
      ]
    }
  },

  sum_loop: {
    label: "Sum 1..10",
    description: "Sums integers from 1 to 10 using a loop.",
    args: {},
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "main",
      "effects": ["IO"],
      "params": [],
      "returns": { "type": "unit" },
      "body": [
        { "op": "let", "id": "total", "type": { "type": "int", "bits": 64, "overflow": "panic" }, "val": { "lit": 0 }, "mut": true },
        {
          "op": "loop",
          "bind": "i",
          "from": { "lit": 1 },
          "to": { "lit": 11 },
          "step": { "lit": 1 },
          "body": [
            { "op": "assign", "id": "total", "val": { "op": "+", "l": { "ref": "total" }, "r": { "ref": "i" } } }
          ]
        },
        {
          "op": "print",
          "val": { "op": "concat", "l": { "lit": "Sum 1..10 = " }, "r": { "op": "int_to_str", "v": { "ref": "total" } } },
          "effect": "IO"
        },
        { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
      ]
    }
  },

  is_even: {
    label: "Is Even?",
    description: "Returns true if n is even. Pass arg n (e.g. 42).",
    args: { n: 42 },
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "is_even",
      "effects": [],
      "params": [
        { "id": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" } }
      ],
      "returns": { "type": "bool" },
      "body": [
        {
          "op": "return",
          "val": { "op": "eq", "l": { "op": "%", "l": { "ref": "n" }, "r": { "lit": 2 } }, "r": { "lit": 0 } }
        }
      ]
    }
  },

  // ── v0.4 Examples ─────────────────────────────────────────────────────────

  type_aliases: {
    label: "Type Aliases",
    group: "v0.4",
    description: "Demonstrates module-level type aliases (v0.4). UserId, Score, and Username are aliases. The rank_label function accepts a Score alias and returns a Username alias.",
    args: {},
    program: {
      "nail": "0.4.0",
      "kind": "module",
      "id": "type_aliases_demo",
      "types": {
        "UserId":   { "type": "int", "bits": 64, "overflow": "panic" },
        "Score":    { "type": "int", "bits": 64, "overflow": "panic" },
        "Username": { "type": "string" }
      },
      "exports": ["main"],
      "defs": [
        {
          "nail": "0.4.0",
          "kind": "fn",
          "id": "rank_label",
          "effects": [],
          "params": [
            { "id": "score", "type": { "type": "alias", "name": "Score" } }
          ],
          "returns": { "type": "alias", "name": "Username" },
          "body": [
            {
              "op": "if",
              "cond": { "op": "gte", "l": { "ref": "score" }, "r": { "lit": 90 } },
              "then": [ { "op": "return", "val": { "lit": "Gold" } } ],
              "else": [
                {
                  "op": "if",
                  "cond": { "op": "gte", "l": { "ref": "score" }, "r": { "lit": 70 } },
                  "then": [ { "op": "return", "val": { "lit": "Silver" } } ],
                  "else": [ { "op": "return", "val": { "lit": "Bronze" } } ]
                }
              ]
            }
          ]
        },
        {
          "nail": "0.4.0",
          "kind": "fn",
          "id": "main",
          "effects": ["IO"],
          "params": [],
          "returns": { "type": "unit" },
          "body": [
            { "op": "let", "id": "uid",   "type": { "type": "alias", "name": "UserId"   }, "val": { "lit": 42 } },
            { "op": "let", "id": "score", "type": { "type": "alias", "name": "Score"    }, "val": { "lit": 85 } },
            {
              "op": "let", "id": "label",
              "type": { "type": "alias", "name": "Username" },
              "val": { "op": "call", "fn": "rank_label", "args": [ { "ref": "score" } ] }
            },
            {
              "op": "print",
              "val": {
                "op": "concat", "l": { "lit": "User #" },
                "r": { "op": "concat", "l": { "op": "int_to_str", "v": { "ref": "uid" } },
                  "r": { "op": "concat", "l": { "lit": " \u2014 Score: " },
                    "r": { "op": "concat", "l": { "op": "int_to_str", "v": { "ref": "score" } },
                      "r": { "op": "concat", "l": { "lit": " \u2192 Rank: " }, "r": { "ref": "label" } }
                    }
                  }
                }
              },
              "effect": "IO"
            },
            { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
          ]
        }
      ]
    }
  },

  fine_grained_effect: {
    label: "Fine-grained FS Effect",
    group: "v0.4",
    description: "Demonstrates structured effect capabilities (v0.4). The function declares { kind: 'FS', allow: ['/tmp/'], ops: ['read'] } — read-only access restricted to /tmp/. Reads /tmp/nail_demo.txt from the server.",
    args: {},
    program: {
      "nail": "0.4.0",
      "kind": "fn",
      "id": "read_demo",
      "effects": [
        { "kind": "FS", "allow": ["/tmp/"], "ops": ["read"] },
        "IO"
      ],
      "params": [],
      "returns": { "type": "unit" },
      "body": [
        {
          "op": "read_file",
          "path": { "lit": "/tmp/nail_demo.txt" },
          "effect": "FS",
          "into": "contents"
        },
        {
          "op": "print",
          "val": { "op": "concat", "l": { "lit": "File says: " }, "r": { "ref": "contents" } },
          "effect": "IO"
        },
        { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
      ]
    }
  },

  // ── v0.5 examples ──────────────────────────────────────────────────────

  enum_adt: {
    label: "Enum / ADT (v0.5)",
    group: "v0.5",
    description: "Algebraic Data Types (v0.5). Defines a Shape enum with Circle and Rectangle variants. enum_make constructs a variant; match_enum dispatches exhaustively with field binding.",
    args: {},
    program: {
      "nail": "0.5.0",
      "kind": "module",
      "id": "shape_demo",
      "exports": ["main"],
      "types": {
        "Shape": {
          "type": "enum",
          "variants": [
            { "tag": "Circle",    "fields": [{ "name": "radius", "type": { "type": "float", "bits": 64 } }] },
            { "tag": "Rectangle", "fields": [{ "name": "w", "type": { "type": "float", "bits": 64 } },
                                              { "name": "h", "type": { "type": "float", "bits": 64 } }] }
          ]
        }
      },
      "defs": [
        {
          "nail": "0.5.0",
          "kind": "fn",
          "id": "main",
          "effects": ["IO"],
          "params": [],
          "returns": { "type": "unit" },
          "body": [
            { "op": "enum_make", "tag": "Circle", "fields": { "radius": { "lit": 3.0 } }, "into": "shape" },
            {
              "op": "match_enum",
              "val": { "ref": "shape" },
              "cases": [
                {
                  "tag": "Circle",
                  "bind": { "r": "radius" },
                  "body": [
                    { "op": "print", "effect": "IO",
                      "val": { "op": "concat", "l": { "lit": "Circle: radius=" },
                               "r": { "op": "int_to_str", "v": { "lit": 3 } } } },
                    { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
                  ]
                },
                {
                  "tag": "Rectangle",
                  "bind": { "width": "w", "height": "h" },
                  "body": [
                    { "op": "print", "effect": "IO", "val": { "lit": "Rectangle" } },
                    { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  },

  stdlib_math: {
    label: "Core StdLib (v0.5)",
    group: "v0.5",
    description: "Core standard library math functions (v0.5): abs, clamp, min2, max2. Pass a negative number to see abs() at work.",
    args: { n: -42 },
    program: {
      "nail": "0.5.0",
      "kind": "fn",
      "id": "main",
      "effects": ["IO"],
      "params": [{ "id": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" } }],
      "returns": { "type": "unit" },
      "body": [
        {
          "op": "let", "id": "a",
          "type": { "type": "int", "bits": 64, "overflow": "panic" },
          "val": { "op": "abs", "val": { "ref": "n" } }
        },
        {
          "op": "let", "id": "clamped",
          "type": { "type": "int", "bits": 64, "overflow": "panic" },
          "val": { "op": "clamp", "val": { "ref": "a" }, "lo": { "lit": 0 }, "hi": { "lit": 100 } }
        },
        {
          "op": "let", "id": "small",
          "type": { "type": "int", "bits": 64, "overflow": "panic" },
          "val": { "op": "min2", "l": { "ref": "a" }, "r": { "lit": 50 } }
        },
        {
          "op": "print", "effect": "IO",
          "val": { "op": "concat", "l": { "lit": "abs(" },
                   "r": { "op": "concat", "l": { "op": "int_to_str", "v": { "ref": "n" } },
                          "r": { "op": "concat", "l": { "lit": ") = " },
                                 "r": { "op": "int_to_str", "v": { "ref": "a" } } } } }
        },
        {
          "op": "print", "effect": "IO",
          "val": { "op": "concat", "l": { "lit": "clamp(a, 0, 100) = " },
                   "r": { "op": "int_to_str", "v": { "ref": "clamped" } } }
        },
        {
          "op": "print", "effect": "IO",
          "val": { "op": "concat", "l": { "lit": "min(a, 50) = " },
                   "r": { "op": "int_to_str", "v": { "ref": "small" } } }
        },
        { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
      ]
    }
  },

  // ── v0.6 examples ──────────────────────────────────────────────────────

  l3_termination: {
    label: "L3 Termination Proof (v0.6)",
    group: "v0.6",
    description: "Level 3 Termination Proof (v0.6). This loop sums 1..n. At L3, NAIL proves the loop terminates because step=1 is a non-zero literal. Run `nail check --level 3` to see the termination certificate.",
    args: { n: 10 },
    program: {
      "nail": "0.6.0",
      "kind": "fn",
      "id": "main",
      "effects": ["IO"],
      "params": [{ "id": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" } }],
      "returns": { "type": "unit" },
      "body": [
        {
          "op": "let", "id": "total",
          "type": { "type": "int", "bits": 64, "overflow": "panic" },
          "val": { "lit": 0 }, "mut": true
        },
        {
          "op": "loop",
          "bind": "i",
          "from": { "lit": 1 },
          "to": { "ref": "n" },
          "step": { "lit": 1 },
          "body": [
            {
              "op": "assign", "id": "total",
              "val": { "op": "+", "l": { "ref": "total" }, "r": { "ref": "i" } }
            }
          ]
        },
        {
          "op": "print", "effect": "IO",
          "val": { "op": "concat", "l": { "lit": "sum(1.." },
                   "r": { "op": "concat", "l": { "op": "int_to_str", "v": { "ref": "n" } },
                          "r": { "op": "concat", "l": { "lit": ") = " },
                                 "r": { "op": "int_to_str", "v": { "ref": "total" } } } } }
        },
        { "op": "return", "val": { "lit": null, "type": { "type": "unit" } } }
      ]
    }
  }
};

// ── DOM Refs ────────────────────────────────────────────────────────────────

const editorEl   = document.getElementById("editor");
const argsEl     = document.getElementById("args-input");
const outputEl   = document.getElementById("output");
const runBtn     = document.getElementById("run-btn");
const exampleSel = document.getElementById("example-select");
const descEl     = document.getElementById("example-desc");
const statusEl   = document.getElementById("status-bar");
const formatBtn  = document.getElementById("format-btn");
const copyBtn    = document.getElementById("copy-btn");
const clearBtn   = document.getElementById("clear-btn");

// ── Helpers ─────────────────────────────────────────────────────────────────

function setStatus(msg, kind = "info") {
  statusEl.textContent = msg;
  statusEl.className = "status-bar " + kind;
}

function showOutput(text, isError = false) {
  outputEl.textContent = text;
  outputEl.className = "output-panel " + (isError ? "error" : "success");
}

function parseArgs(raw) {
  const args = {};
  if (!raw || !raw.trim()) return args;
  for (const part of raw.split(",")) {
    const [k, ...rest] = part.split("=");
    const key = k.trim();
    const val = rest.join("=").trim();
    if (!key) continue;
    // Type coercion: bool → int → float → string
    if (val === "true")  { args[key] = true; continue; }
    if (val === "false") { args[key] = false; continue; }
    const asInt = parseInt(val, 10);
    if (!isNaN(asInt) && String(asInt) === val) { args[key] = asInt; continue; }
    const asFloat = parseFloat(val);
    if (!isNaN(asFloat)) { args[key] = asFloat; continue; }
    args[key] = val;
  }
  return args;
}

function argsToString(args) {
  if (!args || Object.keys(args).length === 0) return "";
  return Object.entries(args).map(([k, v]) => `${k}=${v}`).join(", ");
}

// ── Load Example ─────────────────────────────────────────────────────────────

function loadExample(key) {
  const ex = EXAMPLES[key];
  if (!ex) return;
  editorEl.value = JSON.stringify(ex.program, null, 2);
  argsEl.value = argsToString(ex.args);
  descEl.textContent = ex.description;
  showOutput("", false);
  setStatus(`Loaded: ${ex.label}`, "info");
}

// ── Run ───────────────────────────────────────────────────────────────────────

async function runProgram() {
  let program;
  try {
    program = JSON.parse(editorEl.value);
  } catch (e) {
    showOutput(`JSON parse error: ${e.message}`, true);
    setStatus("Invalid JSON", "error");
    return;
  }

  const args = parseArgs(argsEl.value);
  const body = { program };
  if (Object.keys(args).length > 0) body.args = args;

  runBtn.disabled = true;
  runBtn.textContent = "Running…";
  setStatus("Running NAIL program…", "info");

  const startMs = Date.now();
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    const elapsed = Date.now() - startMs;

    if (data.error && data.output) {
      // Partial output + error
      showOutput(`${data.output}\n\n✗ ${data.error}`, true);
      setStatus(`Error after ${elapsed}ms`, "error");
    } else if (data.error) {
      showOutput(`✗ ${data.error}`, true);
      setStatus(`Error after ${elapsed}ms`, "error");
    } else {
      const out = data.output !== null && data.output !== undefined
        ? (data.output.trim() || "(no output)")
        : "(no output)";
      showOutput(out, false);
      setStatus(`Done in ${elapsed}ms`, "ok");
    }
  } catch (err) {
    showOutput(`✗ Network error: ${err.message}\n\nIs the server running?\n  cd playground\n  python server.py`, true);
    setStatus("Network error", "error");
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "▶ Run";
  }
}

// ── Format JSON ──────────────────────────────────────────────────────────────

function formatJSON() {
  try {
    const parsed = JSON.parse(editorEl.value);
    editorEl.value = JSON.stringify(parsed, null, 2);
    setStatus("Formatted", "ok");
  } catch (e) {
    setStatus(`Cannot format: ${e.message}`, "error");
  }
}

// ── Copy Output ───────────────────────────────────────────────────────────────

function copyOutput() {
  const text = outputEl.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    setStatus("Output copied to clipboard", "ok");
  });
}

// ── Clear Output ──────────────────────────────────────────────────────────────

function clearOutput() {
  showOutput("", false);
  setStatus("Output cleared", "info");
}

// ── Keyboard Shortcut ─────────────────────────────────────────────────────────

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    runProgram();
  }
});

// ── Wire Up Events ────────────────────────────────────────────────────────────

runBtn.addEventListener("click", runProgram);
formatBtn.addEventListener("click", formatJSON);
copyBtn.addEventListener("click", copyOutput);
clearBtn.addEventListener("click", clearOutput);
exampleSel.addEventListener("change", () => loadExample(exampleSel.value));

// ── Populate Dropdown & Load Default ─────────────────────────────────────────

(function init() {
  // Group examples by their optional `group` property; ungrouped go into "Core"
  const groups = {};
  for (const [key, ex] of Object.entries(EXAMPLES)) {
    const g = ex.group || "Core";
    if (!groups[g]) groups[g] = [];
    groups[g].push([key, ex]);
  }

  for (const [groupName, items] of Object.entries(groups)) {
    const grp = document.createElement("optgroup");
    grp.label = groupName;
    for (const [key, ex] of items) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = ex.label;
      grp.appendChild(opt);
    }
    exampleSel.appendChild(grp);
  }

  // Load first example
  const firstKey = Object.keys(EXAMPLES)[0];
  exampleSel.value = firstKey;
  loadExample(firstKey);
})();
