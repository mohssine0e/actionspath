"""Rich console singleton for ActionsPath.

Environment variables:
    ACTIONSPATH_PLAIN=1 (or KUBEPATH_PLAIN=1) - Disable ANSI colors and Rich formatting
    ACTIONSPATH_NO_CLEAR=1 (or KUBEPATH_NO_CLEAR=1) - Prevent screen clearing (content accumulates)

Both are useful for automated testing with pexpect.
"""

from __future__ import annotations

import os
from typing import Optional

from rich.console import Console
from rich.theme import Theme

# Custom theme for ActionsPath
ACTIONSPATH_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "hint": "dim italic",
    "chapter": "bold magenta",
    "points": "bold yellow",
    "progress.complete": "cyan",
    "progress.remaining": "dim",
    # Gamification styles
    "level": "bold yellow",
    "streak": "cyan",
    "celebration": "bold magenta",
})

# Backward compatibility alias
KUBEPATH_THEME = ACTIONSPATH_THEME

# Singleton console instance
_console: Optional[Console] = None


def get_console() -> Console:
    """Get the singleton Rich console instance."""
    global _console
    if _console is None:
        plain_mode = (
            os.environ.get("ACTIONSPATH_PLAIN", "0") == "1"
            or os.environ.get("KUBEPATH_PLAIN", "0") == "1"
        )
        _console = Console(
            theme=ACTIONSPATH_THEME,
            force_terminal=not plain_mode,
            no_color=plain_mode,
        )
    return _console


def clear_screen() -> None:
    """Clear the screen, respecting no-clear mode."""
    console = get_console()
    no_clear = (
        os.environ.get("ACTIONSPATH_NO_CLEAR", "0") == "1"
        or os.environ.get("KUBEPATH_NO_CLEAR", "0") == "1"
    )

    if no_clear:
        # Print separator instead of clearing - allows content to accumulate
        console.print("\n" + "=" * 60 + "\n")
    else:
        console.clear()


def print_banner() -> None:
    """Print the ActionsPath welcome banner."""
    console = get_console()
    console.print(
        "[chapter]"
        r"""
    ___        __  _                 ____        __  __  
   /   | _____/ /_(_)___  ____  _____/ __ \____ _/ /_/ /_ 
  / /| |/ ___/ __/ / __ \/ __ \/ ___/ /_/ / __ `/ __/ __ \
 / ___ / /__/ /_/ / /_/ / / / (__  ) ____/ /_/ / /_/ / / /
/_/  |_\___/\__/_/\____/_/ /_/____/_/    \__,_/\__/_/ /_/ 
"""
        "[/chapter]"
    )
    console.print(
        "[bold cyan]       Hands-on CI/CD and GitHub Actions Terminal Tutor[/bold cyan]\n"
    )
