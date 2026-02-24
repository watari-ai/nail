# NAIL Playground

A minimal browser-based REPL for the [NAIL language](../README.md).

## Features

- **Live JSON editor** — write or paste any valid NAIL program
- **Instant output** — print statements and return values shown side-by-side
- **6 built-in examples** — hello, fibonacci, factorial, countdown, sum loop, is-even
- **Argument support** — pass `n=10, x=42` style args to parameterized functions
- **Dark theme** — easy on the eyes
- **Keyboard shortcut** — `⌘Enter` (Mac) / `Ctrl+Enter` (Linux/Win) to run

## Quick Start

```bash
cd playground

# Install dependencies (only once)
pip install -r requirements.txt

# Start the server
python server.py
```

Then open **http://127.0.0.1:7429** in your browser.

## API

The backend exposes a single endpoint:

### `POST /run`

Request body:
```json
{
  "program": { ...NAIL JSON... },
  "args":    { "n": 10 },       // optional
  "call":    "my_fn"            // optional — for module kind, defaults to "main"
}
```

Success response:
```json
{ "output": "Hello, NAIL\n", "error": null, "return_value": null }
```

Error response:
```json
{ "output": null, "error": "Type error: ..." }
```

### `GET /health`

Returns `{ "status": "ok", "interpreter": "NAIL v0.4" }`.

## Project Structure

```
playground/
├── index.html       — Single-page UI
├── style.css        — Dark theme styles
├── app.js           — Frontend JS (examples embedded)
├── server.py        — FastAPI backend
├── requirements.txt — fastapi, uvicorn
└── README.md        — This file
```

## How It Works

The backend imports the NAIL interpreter directly (no subprocess):

```python
from interpreter import Checker, Runtime
checker = Checker(spec); checker.check()
runtime = Runtime(spec); result = runtime.run(args)
```

`stdout` is captured via `contextlib.redirect_stdout` to collect `print` output.

## Port

Default port: **7429** (configured in `server.py`).
