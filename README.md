# ActionsPath

**Master CI/CD and GitHub Actions in Your Terminal**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)
[![Built with: Rich & Typer](https://img.shields.io/badge/cli-rich%20%7C%20typer-blueviolet.svg)]()

---

## What is ActionsPath?

ActionsPath is an **interactive command-line application** that teaches you CI/CD automation and GitHub Actions right in your terminal. Instead of passively reading documentation, you learn by doing: writing real `.github/workflows/*.yml` files, running linting tools, debugging broken pipelines, and building muscle memory through hands-on practice in ephemeral local Git workspaces.

Whether you are a developer looking to automate testing and deployments, or a DevOps engineer streamlining workflows, ActionsPath provides a structured, gamified learning path that makes mastering GitHub Actions engaging and practical.

---

## Why ActionsPath?

- **Learn by Doing**: Every concept is paired with hands-on practice in an isolated, local Git workspace.
- **Workflow Validation**: Built-in YAML syntax checks, DAG cycle detection, and `actionlint` integration.
- **Real Debugging**: Fix actual broken workflows and misconfigured triggers, runners, and dependencies.
- **Environment Doctor**: Run `actionspath doctor` to inspect local tools (`git`, `gh`, `actionlint`, `act`).
- **AI-Powered Help**: Stuck? Get intelligent hints and progressive guidance powered by Google Gemini.
- **Gamified Progress**: Earn XP, build streaks, unlock levels, and track your curriculum completion.

---

## 4-Section Learning Flow

Each chapter follows a structured four-stage pedagogy:

```
Concepts     ->    Learn core CI/CD theory and workflow syntax
Practice     ->    Run Git, shell, and linting commands in your workspace
Scenarios    ->    Investigate and fix broken GitHub Actions pipelines
Quiz         ->    Reinforce knowledge with interactive questions
```

---

## Quickstart

### 1. Installation

Clone and install using `uv`:

```bash
git clone https://github.com/mohssine/actionspath.git
cd actionspath
uv sync
```

Or install the CLI tool directly:

```bash
uv tool install .
```

### 2. Verify Your Environment

Check local prerequisites:

```bash
actionspath doctor
```

### 3. Start Learning

Launch the interactive terminal interface:

```bash
# Launch interactive main menu
actionspath

# Or jump straight to Chapter 1
actionspath start 1

# Check available chapters
actionspath list
```

---

## Commands

| Command | Description |
|---------|-------------|
| `actionspath` | Open interactive menu with progress dashboard |
| `actionspath start <num>` | Start learning a specific chapter |
| `actionspath practice <num>` | Jump directly to command practice |
| `actionspath scenarios <num>` | Jump directly to debugging scenarios |
| `actionspath list` | Browse all available chapters |
| `actionspath doctor` | Inspect environment and CI/CD tools |
| `actionspath config --set-key` | Set Google Gemini API key for AI hints |
| `actionspath reset --all` | Reset course progress |

---

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
