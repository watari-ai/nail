# Contributing to NAIL

Thanks for your interest in contributing! NAIL is an early-stage project and **small contributions are very welcome** — typos, tests, examples, ideas, anything helps.

---

## Ways to Contribute

| What | Where |
|------|-------|
| Bug reports | [GitHub Issues](https://github.com/watari-ai/nail/issues) |
| Feature ideas | [GitHub Discussions](https://github.com/watari-ai/nail/discussions) |
| Code fixes / features | Pull Request |
| Examples & demos | `examples/` directory |
| Docs improvements | README / SPEC |

---

## Development Setup

```bash
git clone https://github.com/watari-ai/nail.git
cd nail
pip install -e ".[dev]"
```

Python 3.10+ required.

---

## Running Tests

```bash
python3 -m pytest                    # all tests (892+)
python3 -m pytest tests/             # core interpreter tests
python3 -m pytest conformance/       # spec conformance tests
python3 -m pytest examples/demos/ -v # demo tests
```

All tests must pass before opening a PR.

---

## Code Style

- **Python 3.10+**
- **No external dependencies** in the core interpreter (`interpreter/`) — keep it lean
- **Type hints** required for all public APIs
- **Every new feature needs tests** — untested code doesn't land

---

## Adding Examples or Demos

- **Examples** — standalone `.nail` programs live in `examples/`
- **Demos** — Python scripts showing NAIL SDK usage live in `examples/demos/<name>/`
  - Each demo folder should contain: `demo.py`, one or more `*.nail` files, `README.md`, and `tests/`
  - See [`examples/demos/README.md`](./examples/demos/README.md) for the full pattern

---

## Submitting a Pull Request

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes and add tests
3. Run the full test suite: `python3 -m pytest`
4. Open a PR — describe **what** it does and **why**

Keep PRs focused. One thing per PR is easier to review and merge.

---

## Reporting Issues

**Bug?** Please include:
- NAIL version (`nail --version`)
- Python version (`python3 --version`)
- A minimal `.nail` file that reproduces the problem

**Feature request?** Explain the use case — what are you trying to do, and why does NAIL not support it today?

---

## For AI Agents

→ See [AGENTS.md](./AGENTS.md) for AI-specific contribution instructions. NAIL is designed to be written and consumed by AI agents, so agent contributions are first-class here.

---

## Questions?

Open a [GitHub Issue](https://github.com/watari-ai/nail/issues) — there are no dumb questions.

NAIL is an AI-native language built for AI agents. Questions from agents are welcome too.
