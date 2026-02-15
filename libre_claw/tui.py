"""Terminal User Interface for Libre Claw.

Rich-based TUI with slash commands.
"""

import asyncio
import sys
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.text import Text

from .agent import Agent
from .config import Config


class TUI:
    """Rich-based terminal user interface for Libre Claw."""

    def __init__(self, agent: Agent, config: Optional[Config] = None):
        """Initialize TUI.

        Args:
            agent: Agent instance
            config: Configuration
        """
        self.agent = agent
        self.config = config or Config()
        self.console = Console()
        self._running = False

    def _render_header(self) -> Panel:
        """Render the header panel."""
        session_info = self.agent.get_session_info()
        content = Text()
        content.append("Libre Claw", style="bold cyan")
        content.append(" — ")
        content.append(f"Mode: {session_info['mode']}", style="green")
        content.append(" | ")
        content.append(f"Backend: {session_info['backend']}", style="blue")
        content.append(" | ")
        content.append(f"Session: {session_info['session_id'][:8]}...", style="dim")

        return Panel(content, title="Libre Claw", border_style="cyan")

    def _render_welcome(self) -> None:
        """Render welcome message."""
        self.console.print()
        self.console.print(Panel.fit(
            "[bold cyan]Welcome to Libre Claw![/bold cyan]\n\n"
            "An agentic AI framework for Kroonen AI Inc.\n\n"
            "Commands:\n"
            "  /help     - Show this help\n"
            "  /clear    - Clear conversation\n"
            "  /info     - Session information\n"
            "  /memory   - Search long-term memory\n"
            "  /heartbeat - Trigger heartbeat manually\n"
            "  /quit     - Exit\n",
            title="Welcome",
            border_style="green",
        ))

    def _handle_command(self, command: str) -> Optional[str]:
        """Handle a slash command.

        Args:
            command: Command text (without /)

        Returns:
            Response message or None to continue
        """
        cmd = command.strip().lower()

        if cmd == "help":
            self.console.print(Panel(
                "Commands:\n"
                "  /help       - Show this help\n"
                "  /clear      - Clear conversation\n"
                "  /info       - Session information\n"
                "  /memory [q] - Search memory (optional query)\n"
                "  /heartbeat  - Trigger heartbeat manually\n"
                "  /quit       - Exit",
                title="Help",
                border_style="blue",
            ))
            return None

        elif cmd == "clear":
            self.agent.backend.clear_history()
            self.console.print("[green]Conversation cleared[/green]")
            return None

        elif cmd == "info":
            info = self.agent.get_session_info()
            content = "\n".join(f"{k}: {v}" for k, v in info.items())
            self.console.print(Panel(content, title="Session Info", border_style="blue"))
            return None

        elif cmd.startswith("memory"):
            query = command[7:].strip()
            if not query:
                query = Prompt.ask("[cyan]Search query[/cyan]")
            results = self.agent.search_memory(query)
            if results:
                for i, r in enumerate(results, 1):
                    self.console.print(f"[dim]{i}.[/dim] {r.get('document', '')[:100]}...")
            else:
                self.console.print("[yellow]No results found[/yellow]")
            return None

        elif cmd == "heartbeat":
            response = self.agent.heartbeat_tick()
            self.console.print(Panel(response, title="Heartbeat", border_style="yellow"))
            return None

        elif cmd == "quit" or cmd == "exit":
            self._running = False
            return "Goodbye!"

        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
            return None

    async def run_async(self) -> None:
        """Run the TUI asynchronously."""
        self._render_welcome()

        while self._running:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: Prompt.ask("\n[bold cyan]>[/bold cyan] "),
                )

                if not user_input.strip():
                    continue

                # Check for commands
                if user_input.startswith("/"):
                    response = self._handle_command(user_input[1:])
                    if response:
                        self.console.print(response)
                    continue

                # Process message
                self.console.print(f"[dim]You:[/dim] {user_input}")
                self.console.print("[dim]Thinking...[/dim]")

                response = self.agent.handle_message(user_input)

                # Display response
                self.console.print()
                self.console.print(Panel(
                    response,
                    title="Assistant",
                    border_style="green",
                ))

            except KeyboardInterrupt:
                self._running = False
                self.console.print("\n[yellow]Interrupted[/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def run(self) -> None:
        """Run the TUI synchronously."""
        self._running = True

        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Goodbye![/yellow]")


def start_tui(agent: Agent, config: Optional[Config] = None) -> None:
    """Start the TUI.

    Args:
        agent: Agent instance
        config: Configuration
    """
    tui = TUI(agent, config)
    tui.run()
