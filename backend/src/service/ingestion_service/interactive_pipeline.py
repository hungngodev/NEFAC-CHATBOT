"""
NEFAC Interactive Pipeline Manager - ALL-IN-ONE
Provides multiple interface options for start/stop controls of the document ingestion pipeline:
1. Basic Interface (no dependencies) - Terminal menu system
2. Rich Interface (requires 'rich') - Colored output with live tables  
3. Textual Interface (requires 'textual') - Full TUI with buttons and progress bars

Usage:
    python interactive_pipeline.py
"""

import asyncio
import logging
import os
import signal
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Optional

# Rich imports
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

# Textual imports
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Log, ProgressBar

# Add the backend src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

# Import database cleaner
from backend.src.service.ingestion_service.index.database_cleaner import clear_all_databases


class PipelineStatus(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class FileTypeStatus:
    def __init__(self, name: str):
        self.name = name
        self.status = PipelineStatus.IDLE
        self.processed = 0
        self.total = 0
        self.start_time: Optional[float] = None
        self.error_message = ""


class BasePipelineManager:
    """Base pipeline manager with common functionality"""

    def __init__(self):
        self.status = PipelineStatus.IDLE
        self.file_types = {"html": FileTypeStatus("HTML"), "pdf": FileTypeStatus("PDF"), "youtube": FileTypeStatus("YouTube")}
        self.stop_requested = False
        self.current_thread: Optional[threading.Thread] = None

    def start_pipeline(self, file_types: list = None, limit: int = None, clear_databases: bool = True):
        """Start the pipeline"""
        if self.status == PipelineStatus.RUNNING:
            return False

        self.status = PipelineStatus.RUNNING
        self.stop_requested = False

        # Reset file type statuses
        for ft_status in self.file_types.values():
            ft_status.status = PipelineStatus.IDLE
            ft_status.processed = 0
            ft_status.start_time = None
            ft_status.error_message = ""

        # Start processing in background thread
        self.current_thread = threading.Thread(target=self._run_pipeline, args=(file_types or ["html", "pdf", "youtube"], limit, clear_databases), daemon=True)
        self.current_thread.start()
        return True

    def stop_pipeline(self):
        """Stop the pipeline"""
        if self.status == PipelineStatus.RUNNING:
            self.status = PipelineStatus.STOPPING
            self.stop_requested = True
            return True
        return False

    def _run_pipeline(self, file_types: list, limit: int, clear_databases: bool):
        """Run the pipeline in background thread"""
        try:
            # Import here to avoid circular imports
            from src.service.ingestion_service.processing import LoaderService, main_pipeline

            # Clear databases if requested
            if clear_databases and not self.stop_requested:
                clear_all_databases()

            if self.stop_requested:
                self._complete_with_status(PipelineStatus.STOPPED)
                return

            loader_service = LoaderService(logging.getLogger("pipeline"))

            for file_type in file_types:
                if self.stop_requested:
                    self._complete_with_status(PipelineStatus.STOPPED)
                    return

                ft_status = self.file_types[file_type]
                ft_status.status = PipelineStatus.RUNNING
                ft_status.start_time = time.time()

                try:
                    # Get metadata path
                    metadata_path = loader_service.get_default_metadata_path(file_type)
                    if not metadata_path:
                        ft_status.status = PipelineStatus.ERROR
                        ft_status.error_message = f"No metadata path for {file_type}"
                        continue

                    # Run pipeline for this file type
                    processed_count = main_pipeline(metadata_path, file_type, limit)

                    if not self.stop_requested:
                        ft_status.status = PipelineStatus.COMPLETED
                        ft_status.processed = processed_count
                    else:
                        ft_status.status = PipelineStatus.STOPPED

                except Exception as e:
                    ft_status.status = PipelineStatus.ERROR
                    ft_status.error_message = str(e)[:50]

            if not self.stop_requested:
                self._complete_with_status(PipelineStatus.COMPLETED)
            else:
                self._complete_with_status(PipelineStatus.STOPPED)

        except Exception:
            self._complete_with_status(PipelineStatus.ERROR)

    def _complete_with_status(self, status: PipelineStatus):
        """Complete pipeline with given status"""
        self.status = status
        self.stop_requested = False


# =============================================================================
# BASIC INTERFACE (No Dependencies)
# =============================================================================


class BasicPipelineManager(BasePipelineManager):
    """Basic pipeline manager with simple terminal interface"""

    def __init__(self):
        super().__init__()
        self.running = True

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system("cls" if os.name == "nt" else "clear")

    def print_header(self):
        """Print the application header"""
        print("=" * 60)
        print("🚀 NEFAC DOCUMENT INGESTION PIPELINE")
        print("=" * 60)

    def print_status(self):
        """Print current status"""
        self.clear_screen()
        self.print_header()

        # Overall status
        status_color = {PipelineStatus.IDLE: "⚪", PipelineStatus.RUNNING: "🟢", PipelineStatus.STOPPING: "🟡", PipelineStatus.STOPPED: "🟡", PipelineStatus.COMPLETED: "✅", PipelineStatus.ERROR: "❌"}

        print(f"\n📊 Overall Status: {status_color.get(self.status, '⚪')} {self.status.value}")
        print("-" * 40)

        # File type statuses
        print("\n📄 File Type Status:")
        for file_type, ft_status in self.file_types.items():
            icon = status_color.get(ft_status.status, "⚪")
            elapsed = ""
            if ft_status.start_time and ft_status.status == PipelineStatus.RUNNING:
                elapsed = f" ({time.time() - ft_status.start_time:.1f}s)"
            elif ft_status.status == PipelineStatus.COMPLETED:
                elapsed = f" ({ft_status.processed} docs)"
            elif ft_status.status == PipelineStatus.ERROR and ft_status.error_message:
                elapsed = f" (Error: {ft_status.error_message})"

            print(f"  {icon} {ft_status.name:<8} - {ft_status.status.value}{elapsed}")

        print("\n" + "-" * 40)

    def print_menu(self):
        """Print the command menu"""
        print("\n🎮 Commands:")
        print("  [1] start    - Start processing all file types")
        print("  [2] stop     - Stop current processing")
        print("  [3] status   - Refresh status display")
        print("  [4] clear    - Clear databases")
        print("  [5] help     - Show detailed help")
        print("  [q] quit     - Exit application")
        print("\n" + "=" * 60)

    def start_interactive_mode(self):
        """Start the interactive mode"""
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)

        while self.running:
            try:
                self.print_status()
                self.print_menu()

                command = input("Enter command: ").strip().lower()

                if command in ["q", "quit", "exit"]:
                    if self.status == PipelineStatus.RUNNING:
                        print("\n⚠️  Pipeline is running. Stop it first? (y/n): ", end="")
                        confirm = input().strip().lower()
                        if confirm in ["y", "yes"]:
                            self.stop_pipeline()
                            print("Waiting for pipeline to stop...")
                            time.sleep(3)
                        else:
                            continue
                    self.running = False

                elif command in ["1", "start"]:
                    if self.start_pipeline():
                        print("\n🚀 Pipeline started in background!")
                    else:
                        print("\n⚠️  Pipeline is already running!")
                    time.sleep(1)

                elif command in ["2", "stop"]:
                    if self.stop_pipeline():
                        print("\n🛑 Stop signal sent. Pipeline will stop after current operation.")
                    else:
                        print("\n⚠️  Pipeline is not running")
                    time.sleep(1)

                elif command in ["3", "status"]:
                    # Just refresh the display
                    continue

                elif command in ["4", "clear"]:
                    self.clear_databases()

                elif command in ["5", "help"]:
                    self.show_help()

                else:
                    print(f"\n❌ Unknown command: '{command}'")
                    input("Press Enter to continue...")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

        print("\n👋 Goodbye!")

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n🛑 Interrupt received...")
        if self.status == PipelineStatus.RUNNING:
            print("Stopping pipeline...")
            self.stop_pipeline()
            time.sleep(2)
        self.running = False
        print("👋 Goodbye!")
        sys.exit(0)

    def clear_databases(self):
        """Clear databases"""
        if self.status == PipelineStatus.RUNNING:
            print("\n⚠️  Cannot clear databases while pipeline is running")
            input("Press Enter to continue...")
            return

        print("\n🗑️  Clearing databases...")
        try:
            clear_results = clear_all_databases()

            failed_dbs = [db for db, success in clear_results.items() if not success]
            if failed_dbs:
                print(f"⚠️  Failed to clear some databases: {', '.join(failed_dbs)}")
            else:
                print("✅ Successfully cleared all databases")
        except Exception as e:
            print(f"❌ Error clearing databases: {e}")

        input("Press Enter to continue...")

    def show_help(self):
        """Show help information"""
        self.clear_screen()
        print("=" * 60)
        print("📖 HELP - NEFAC PIPELINE MANAGER")
        print("=" * 60)

        help_text = """
🎯 PURPOSE:
This tool manages the NEFAC document ingestion pipeline interactively.
You can start, stop, and monitor the processing of documents.

📋 FILE TYPES PROCESSED:
• HTML - Web content and articles
• PDF  - Document files  
• YouTube - Video transcripts

🎮 COMMANDS:
• start  - Begin processing all file types
• stop   - Gracefully stop current processing
• status - Refresh the status display
• clear  - Clear all databases (when not running)
• help   - Show this help screen
• quit   - Exit the application

💡 TIPS:
• Pipeline runs in background - you can check status anytime
• Use Ctrl+C for emergency stop
• Always stop pipeline before clearing databases
• Processing is resumed-safe - you can restart anytime

⚠️  NOTES:
• Stopping may take a few seconds to complete current operation
• Database clearing removes all indexed content
• Progress is shown in real-time during processing
        """

        print(help_text)
        print("=" * 60)
        input("Press Enter to return to main menu...")


# =============================================================================
# RICH INTERFACE (Requires 'rich' library)
# =============================================================================


class RichPipelineManager(BasePipelineManager):
    """Rich pipeline manager with colored output and live tables"""

    def __init__(self):
        super().__init__()
        self.console = Console()
        self.Rich = True

    def create_status_table(self):
        """Create status table for display"""
        table = Table(title="📊 NEFAC Document Ingestion Pipeline")
        table.add_column("File Type", style="cyan", no_wrap=True)
        table.add_column("Status", style="magenta")
        table.add_column("Processed", justify="right", style="green")

        for file_type, ft_status in self.file_types.items():
            status_text = ft_status.status.value.title()
            color = {PipelineStatus.IDLE: "white", PipelineStatus.RUNNING: "green", PipelineStatus.STOPPING: "yellow", PipelineStatus.STOPPED: "yellow", PipelineStatus.COMPLETED: "green", PipelineStatus.ERROR: "red"}.get(ft_status.status, "white")

            table.add_row(ft_status.name, Text(status_text, style=color), f"{ft_status.processed}")

        return table

    def create_layout(self):
        """Create the layout for the display"""
        layout = Layout()

        # Main status
        main_status = f"Pipeline Status: {self.status.value.title()}"
        status_panel = Panel(main_status, title="Status", border_style="blue")

        # File types table
        table = self.create_status_table()

        # Controls
        controls = """
🚀 Commands:
  [bold green]start[/bold green] - Start processing all file types
  [bold red]stop[/bold red]  - Stop current processing
  [bold yellow]status[/bold yellow] - Show current status
  [bold blue]clear[/bold blue] - Clear databases
  [bold magenta]quit[/bold magenta]  - Exit application
        """
        controls_panel = Panel(controls, title="Controls", border_style="green")

        layout.split_column(Layout(status_panel, size=3), Layout(table, size=10), Layout(controls_panel, size=8))

        return layout

    def start_interactive_mode(self):
        """Start the rich interactive mode"""
        self.console.print("[bold blue]🚀 NEFAC Rich Interactive Pipeline Manager[/bold blue]")
        self.console.print("Type commands or 'quit' to exit\n")

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)

        with Live(self.create_layout(), refresh_per_second=2, console=self.console) as live:
            self.live = live

            while True:
                try:
                    # Update display
                    live.update(self.create_layout())

                    # Get user input
                    self.console.print("\n[bold cyan]Command:[/bold cyan] ", end="")
                    command = input().strip().lower()

                    if command in ["quit", "exit", "q"]:
                        if self.status == PipelineStatus.RUNNING:
                            if Confirm.ask("Pipeline is running. Stop and quit?"):
                                self.stop_pipeline()
                                time.sleep(2)
                                break
                        else:
                            break

                    elif command in ["start", "s"]:
                        if self.start_pipeline():
                            self.console.print("[green]🚀 Pipeline started![/green]")
                        else:
                            self.console.print("[yellow]Pipeline is already running![/yellow]")

                    elif command in ["stop", "x"]:
                        if self.stop_pipeline():
                            self.console.print("[yellow]⏹️  Stopping pipeline...[/yellow]")
                        else:
                            self.console.print("[yellow]Pipeline is not running[/yellow]")

                    elif command in ["status", "st"]:
                        # Just refresh the display
                        continue

                    elif command in ["clear", "c"]:
                        self.clear_databases()

                    elif command in ["help", "h"]:
                        self.show_help()

                    else:
                        self.console.print(f"[red]Unknown command: {command}[/red]")

                except KeyboardInterrupt:
                    break
                except EOFError:
                    break

        self.console.print("\n[bold blue]👋 Goodbye![/bold blue]")

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        if self.status == PipelineStatus.RUNNING:
            self.console.print("\n[yellow]Stopping pipeline...[/yellow]")
            self.stop_pipeline()
        else:
            self.console.print("\n[bold blue]👋 Goodbye![/bold blue]")
            sys.exit(0)

    def clear_databases(self):
        """Clear databases"""
        if self.status == PipelineStatus.RUNNING:
            self.console.print("[yellow]Cannot clear databases while pipeline is running[/yellow]")
            return

        try:
            self.console.print("[yellow]🗑️  Clearing databases...[/yellow]")
            clear_results = clear_all_databases()

            failed_dbs = [db for db, success in clear_results.items() if not success]
            if failed_dbs:
                self.console.print(f"[red]⚠️  Failed to clear some databases: {', '.join(failed_dbs)}[/red]")
            else:
                self.console.print("[green]✅ Successfully cleared all databases[/green]")
        except Exception as e:
            self.console.print(f"[red]❌ Error clearing databases: {e}[/red]")

    def show_help(self):
        """Show help information"""
        help_text = """
[bold blue]📖 Available Commands:[/bold blue]

[bold green]start[/bold green] or [bold green]s[/bold green]      - Start processing all file types
[bold red]stop[/bold red] or [bold red]x[/bold red]       - Stop current processing  
[bold yellow]status[/bold yellow] or [bold yellow]st[/bold yellow]    - Show detailed status
[bold blue]clear[/bold blue] or [bold blue]c[/bold blue]      - Clear databases only
[bold magenta]help[/bold magenta] or [bold magenta]h[/bold magenta]       - Show this help
[bold cyan]quit[/bold cyan] or [bold cyan]q[/bold cyan]       - Exit application

[bold blue]💡 Tips:[/bold blue]
- Use Ctrl+C to interrupt and stop gracefully
- The display updates automatically
- Processing runs in the background
        """
        self.console.print(Panel(help_text, title="Help", border_style="blue"))


# =============================================================================
# TEXTUAL INTERFACE (Requires 'textual' library)
# =============================================================================


class TextualPipelineManager(BasePipelineManager):
    """Textual pipeline manager with full TUI interface"""

    def __init__(self):
        super().__init__()
        self.Textual = True

    def start_interactive_mode(self):
        """Start the textual TUI mode"""

        class PipelineApp(App[None]):
            CSS = """
            .status-box { border: solid $primary; padding: 1; margin: 1; }
            .file-type-box { border: solid $secondary; padding: 1; margin: 1; height: 6; }
            .controls { dock: bottom; height: 5; background: $surface; }
            .status-idle { color: $text; }
            .status-running { color: $success; }
            .status-stopping { color: $warning; }
            .status-stopped { color: $warning; }
            .status-completed { color: $success; }
            .status-error { color: $error; }
            """

            BINDINGS = [("q", "quit", "Quit"), ("s", "start_pipeline", "Start"), ("x", "stop_pipeline", "Stop")]

            def __init__(self, manager):
                super().__init__()
                self.manager = manager

            def compose(self) -> ComposeResult:
                yield Header(show_clock=True)
                with Container():
                    with Vertical():
                        with Container(classes="status-box"):
                            yield Label("📊 Pipeline Status", id="status-title")
                            yield Label("Idle", id="status-label", classes="status-idle")
                        with Horizontal():
                            for file_type in ["html", "pdf", "youtube"]:
                                with Container(classes="file-type-box"):
                                    yield Label(f"📄 {file_type.upper()}", id=f"{file_type}-title")
                                    yield Label("Idle", id=f"{file_type}-status", classes="status-idle")
                                    yield Label("0/0 processed", id=f"{file_type}-progress")
                                    yield ProgressBar(total=100, show_eta=False, id=f"{file_type}-bar")
                        yield Log(highlight=True, markup=True, id="logs")
                    with Container(classes="controls"):
                        with Horizontal():
                            yield Button("🚀 Start All", id="start-all", variant="success")
                            yield Button("⏹️  Stop", id="stop", variant="error")
                            yield Button("🗑️  Clear Logs", id="clear-logs")
                            yield Button("🔄 Clear Databases", id="clear-db")
                            yield Button("❌ Quit", id="quit", variant="warning")
                yield Footer()

            def on_mount(self) -> None:
                self.update_status("Ready to start processing")

            @on(Button.Pressed, "#start-all")
            async def start_all(self) -> None:
                if self.manager.start_pipeline():
                    self.update_status("Pipeline started!")
                else:
                    self.update_status("Pipeline is already running")

            @on(Button.Pressed, "#stop")
            async def stop_pipeline(self) -> None:
                if self.manager.stop_pipeline():
                    self.update_status("Stopping pipeline...")
                else:
                    self.update_status("Pipeline is not running")

            @on(Button.Pressed, "#clear-logs")
            async def clear_logs(self) -> None:
                self.query_one("#logs", Log).clear()

            @on(Button.Pressed, "#clear-db")
            async def clear_databases(self) -> None:
                if self.manager.status == PipelineStatus.RUNNING:
                    self.update_status("Cannot clear databases while pipeline is running")
                    return
                try:
                    clear_results = clear_all_databases()
                    failed_dbs = [db for db, success in clear_results.items() if not success]
                    if failed_dbs:
                        self.update_status(f"Failed to clear some databases: {', '.join(failed_dbs)}")
                    else:
                        self.update_status("Successfully cleared all databases")
                except Exception as e:
                    self.update_status(f"Error clearing databases: {e}")

            @on(Button.Pressed, "#quit")
            async def quit_app(self) -> None:
                if self.manager.status == PipelineStatus.RUNNING:
                    self.manager.stop_pipeline()
                    await asyncio.sleep(1)
                self.exit()

            def update_status(self, message: str) -> None:
                status_label = self.query_one("#status-label", Label)
                log_widget = self.query_one("#logs", Log)
                status_label.update(message)
                timestamp = time.strftime("%H:%M:%S")
                log_widget.write_line(f"[{timestamp}] {message}")

        app = PipelineApp(self)
        app.run()


# =============================================================================
# MAIN LAUNCHER
# =============================================================================


def main():
    """Main launcher that detects available libraries and offers interface choices"""
    print("🚀 NEFAC Document Ingestion Pipeline")
    print("=" * 50)
    print()

    # Detect available interfaces
    available_interfaces = []

    # Basic interface (always available)
    available_interfaces.append(("Basic Interface", "No dependencies required", BasicPipelineManager))

    # Rich interface
    available_interfaces.append(("Rich Interface", "Colored output with live tables", RichPipelineManager))

    # Textual interface
    available_interfaces.append(("Textual Interface", "Full GUI-like TUI experience", TextualPipelineManager))

    print("Available interfaces:")
    for i, (name, desc, _) in enumerate(available_interfaces, 1):
        print(f"{i}. {name} - {desc}")

    print(f"{len(available_interfaces) + 1}. Exit")
    print()

    try:
        choice = int(input("Select interface (1-{}): ".format(len(available_interfaces) + 1)).strip())

        if 1 <= choice <= len(available_interfaces):
            name, desc, manager_class = available_interfaces[choice - 1]
            print(f"\n🚀 Starting {name}...")
            print(f"📝 {desc}")
            print("-" * 50)

            try:
                manager = manager_class()
                manager.start_interactive_mode()
            except ImportError as e:
                print(f"❌ Error: {e}")
                print("Falling back to Basic Interface...")
                manager = BasicPipelineManager()
                manager.start_interactive_mode()

        elif choice == len(available_interfaces) + 1:
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice")

    except (ValueError, KeyboardInterrupt):
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
