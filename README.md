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
- **6 Capstone Boss Labs**: Multi-objective incident missions at the end of each module to earn enterprise certification titles.
- **Active Recall Quizzes**: 30 `fill_yaml` schema completion challenges test real YAML syntax without multiple-choice guessing.
- **Environment Doctor**: Run `actionspath doctor` to inspect local tools (`git`, `gh`, `actionlint`, `act`).
- **AI-Powered Help**: Stuck? Get intelligent hints and progressive guidance powered by Google Gemini.
- **Gamified Progress**: Earn XP, build streaks, unlock levels, and track your curriculum completion.

---

## Learning Flow

Each module guides you through structured chapters followed by an end-of-module capstone:

```
Chapters (1-5)  ──►  Concepts ──► Practice ──► Broken Scenarios ──► Active Recall
      │
      ▼
👑 BOSS LAB     ──►  End-of-Module Incident Response & Enterprise Certification
```

---

## 👑 Module Boss Labs

At the end of each module, test your skills against realistic production incidents:

| Module | Command | Mission Focus | Title Earned |
|:---|:---|:---|:---|
| **1. Foundations** | `actionspath lab 1` | *The Black Friday Incident* (Triage runner logs & DAG cycles) | `Certified CI Operator` |
| **2. Runners & Matrix** | `actionspath lab 2` | *The 5x Pipeline Accelerator* (14 GB disk reclaim & matrix cache) | `Runner & Matrix Specialist` |
| **3. Releases & Monorepos** | `actionspath lab 3` | *The Monorepo Release* (Path filters & artifact v4 namespaces) | `Release Engineer` |
| **4. Security & OIDC** | `actionspath lab 4` | *The Red-Team Security Audit* (Eliminate PwnRequest & static keys) | `DevSecOps Architect` |
| **5. Custom Actions** | `actionspath lab 5` | *The Internal Developer Platform* (Blank-canvas Composite Action) | `Platform Tooling Engineer` |
| **6. Enterprise Deploy** | `actionspath lab 6` | *Zero-Downtime Blue-Green* (Canary metric gates & automated rollback) | `Master CI/CD Architect` |

---

## Quickstart

### 1. Installation

Install directly using `uv`:

```bash
uv tool install git+https://github.com/mohssine0e/actionspath.git
```

Or clone and run locally:

```bash
git clone https://github.com/mohssine0e/actionspath.git
cd actionspath
uv sync
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

# Launch a Module Boss Lab
actionspath lab 1

# Browse all available chapters and labs
actionspath list
```

---

## Commands

| Command | Description |
|---------|-------------|
| `actionspath` | Open interactive menu with progress dashboard |
| `actionspath start <num>` | Start learning a specific chapter (1-30) |
| `actionspath lab <module>` | Launch an end-of-module capstone Boss Lab (1-6) |
| `actionspath practice <num>` | Jump directly to command practice |
| `actionspath scenarios <num>` | Jump directly to debugging scenarios |
| `actionspath list` | Browse all available chapters and Boss Labs |
| `actionspath doctor` | Inspect environment and CI/CD tools |
| `actionspath config --set-key` | Set Google Gemini API key for AI hints |
| `actionspath reset --all` | Reset course progress |

---

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
