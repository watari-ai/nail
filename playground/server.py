"""
NAIL Playground — FastAPI Backend
POST /run  →  {"program": <nail_json>}
           ←  {"output": "...", "error": null}
              or {"output": null, "error": "..."}
"""

import sys
import io
import json
from pathlib import Path
from contextlib import redirect_stdout

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any

# ── NAIL interpreter lives one directory up ───────────────────────────────
NAIL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(NAIL_ROOT))

from interpreter import Checker, Runtime, CheckError, NailTypeError, NailEffectError, NailRuntimeError
from interpreter.runtime import UNIT

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(title="NAIL Playground", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    program: Any            # The NAIL program JSON
    call: str | None = None # Optional: function name to call (module kind)
    args: dict | None = None # Optional: arguments to pass


class RunResponse(BaseModel):
    output: str | None
    error: str | None
    return_value: str | None = None


@app.post("/run", response_model=RunResponse)
def run_program(req: RunRequest):
    spec = req.program

    if not isinstance(spec, dict):
        return RunResponse(output=None, error="Program must be a JSON object (dict)")

    # ── Type-check ──────────────────────────────────────────────────────
    try:
        checker = Checker(spec)
        checker.check()
    except CheckError as e:
        return RunResponse(output=None, error=f"Schema error: {e}")
    except NailTypeError as e:
        return RunResponse(output=None, error=f"Type error: {e}")
    except NailEffectError as e:
        return RunResponse(output=None, error=f"Effect error: {e}")
    except Exception as e:
        return RunResponse(output=None, error=f"Check error: {e}")

    # ── Run ─────────────────────────────────────────────────────────────
    captured = io.StringIO()
    try:
        runtime = Runtime(spec)
        kind = spec.get("kind")
        args = req.args or {}

        with redirect_stdout(captured):
            if kind == "module":
                fn_name = req.call or "main"
                result = runtime.run_fn(fn_name, args)
            else:
                result = runtime.run(args if args else None)

        output = captured.getvalue()

        # Format non-unit return values
        ret_str = None
        if result is not UNIT and result is not None:
            ret_str = f"→ {result}"

        # Combine output lines with return value
        full_output = output
        if ret_str:
            if full_output and not full_output.endswith("\n"):
                full_output += "\n"
            full_output += ret_str

        return RunResponse(
            output=full_output if full_output else "",
            error=None,
            return_value=ret_str,
        )

    except NailRuntimeError as e:
        partial = captured.getvalue()
        return RunResponse(
            output=partial if partial else None,
            error=f"Runtime error: {e}",
        )
    except Exception as e:
        partial = captured.getvalue()
        return RunResponse(
            output=partial if partial else None,
            error=f"Unexpected error: {e}",
        )


@app.get("/health")
def health():
    return {"status": "ok", "interpreter": "NAIL v0.1"}


# ── Serve static files ─────────────────────────────────────────────────────
playground_dir = Path(__file__).parent
app.mount("/", StaticFiles(directory=str(playground_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7429, log_level="info")
