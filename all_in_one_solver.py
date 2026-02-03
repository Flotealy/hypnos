import os
import subprocess
import threading
import time
import sys
import re
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.prompt import Prompt
from rich.text import Text
from rich import box
import getpass

# --- Configuration ---
EMAIL = os.environ.get("EMAIL")
PASSWORD = os.environ.get("PASSWORD")

# Paths to the scripts
SOLVERS = {
    "background": [
        {"name": "2048", "path": "src/hypnos/twothousandfortyeight/solve.py"},
        {"name": "Minesweeper", "path": "src/hypnos/minesweeper/solver.py"},
        {"name": "Wordle", "path": "src/hypnos/wordle/solve.py"},
    ],
    "sequential": [
        {"name": "Breakout (Score Spam)", "path": "src/hypnos/breakout/spam_score.py"},
        {"name": "Kahoot", "path": "src/hypnos/kahoot/solve.py"},
        {"name": "QR Hunt", "path": "src/hypnos/qrcode/solver.py"},
        {"name": "Snake", "path": "src/hypnos/snake/solve.py"},
        {"name": "Sporcle", "path": "src/hypnos/sporcle/solve.py"},
        {"name": "Tetris", "path": "src/hypnos/tetris/solve.py"},
        {"name": "Trivia", "path": "src/hypnos/trivia/solve.py", "args": ["solve"]},
        {"name": "Typing", "path": "src/hypnos/typing/solver.py"},
    ]
}

# State management
app_state = {
    "background": {}, # name -> {status, last_stat, process}
    "sequential": {
        "current": None, 
        "history": [] # {name, status, result}
    },
    "running": True
}

console = Console()

def parse_stat(name, line):
    """Refined parser for sub-process stdout to extract meaningful status."""
    line = line.strip()
    # Patterns for specific games
    if "Score:" in line or "Total Score:" in line or "TOTAL SCORE:" in line:
        return f"Score: {line.split(':')[-1].strip()}"
    if "Wins:" in line or "Losses:" in line:
        return line.split(']')[-1].strip() if ']' in line else line
    if "WPM:" in line:
        return line.split('Stats:')[-1].strip() if 'Stats:' in line else line
    if "SUCCÈS pour" in line or "Code" in line and "OK" in line:
        return f"[bold green]Code OK[/bold green]"
    if "DÉJÀ TROUVÉ" in line or "already_found" in line or "ALREADY FOUND" in line:
        return "[bold green]ALREADY FOUND[/bold green]"
    if "SUCCESS" in line or "VICTORY" in line or "VICTOIRE" in line or "COMPLETED" in line:
        return "[bold green]SUCCESS[/bold green]"
    if "FAILED" in line or "GAME OVER" in line or "PERDU" in line or "Error" in line:
        return "[bold red]FAILED[/bold red]"
    if "Finished" in line and "in" in line:
        return line.split("Finished")[-1].strip()
    if "Points:" in line:
        return f"Points: {line.split('Points:')[-1].strip()}"
    if "Simulating human typing" in line:
        return "[yellow]Typing...[/yellow]"
    if "Solving Theme:" in line:
        return f"Theme: {line.split('Theme:')[-1].strip()}"
    if "Loaded" in line and "answers" in line:
        return f"Ready ({line.split('Loaded')[-1].strip()})"
    return None

def run_solver_thread(name, path, is_background=True, args=None):
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    log_file_path = f"logs/{name.lower().replace(' ', '_')}.log"
    
    env = os.environ.copy()
    env["EMAIL"] = EMAIL or ""
    env["PASSWORD"] = PASSWORD or ""
    env["SOLVE_ONCE"] = "0" if is_background else "1"
    env["PYTHONUNBUFFERED"] = "1"
    
    cmd = [sys.executable, path]
    if args:
        cmd.extend(args)
        
    try:
        with open(log_file_path, "a", encoding="utf-8") as log_f:
            log_f.write(f"\n--- Starting {name} at {time.ctime()} ---\n")
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            if is_background:
                app_state["background"][name] = {"status": "Running", "last_stat": "-", "process": process}
            else:
                app_state["sequential"]["current"] = {"name": name, "status": "Solving", "last_stat": "-"}
                
            for line in process.stdout:
                log_f.write(line)
                log_f.flush()
                stat = parse_stat(name, line)
                if stat:
                    if is_background:
                        app_state["background"][name]["last_stat"] = stat
                    else:
                        app_state["sequential"]["current"]["last_stat"] = stat
                
            process.wait()
            
            if is_background:
                app_state["background"][name]["status"] = f"Finished ({process.returncode}) - Waiting 15s"
                # Auto-restart background games if the main script is still running
                if app_state["running"]:
                    time.sleep(15) # Safety buffer for rate limits
                    run_solver_thread(name, path, is_background, args)
            else:
                curr = app_state["sequential"]["current"]
                result = curr["last_stat"] if curr else "-"
                
                # Logic to determine if it was a real success
                status = "[bold green]COMPLETED[/bold green]"
                if "FAILED" in result or "Error" in result or process.returncode != 0:
                    status = "[bold red]FAILED[/bold red]"
                
                app_state["sequential"]["history"].append({
                    "name": name, 
                    "status": status, 
                    "result": result
                })
                app_state["sequential"]["current"] = None
            
    except Exception as e:
        status_msg = f"[bold red]Error[/bold red]"
        err_detail = str(e)
        if is_background:
            app_state["background"][name] = {"status": status_msg, "last_stat": err_detail}
        else:
            app_state["sequential"]["history"].append({
                "name": name, 
                "status": status_msg, 
                "result": err_detail
            })
            app_state["sequential"]["current"] = None

def make_dashboard():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    
    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )

    # Header
    header_content = Text.from_markup(f" [bold cyan]Hypnos All-In-One Solver[/bold cyan] | User: [yellow]{EMAIL}[/yellow] | Time: {time.strftime('%H:%M:%S')}")
    layout["header"].update(Panel(header_content, box=box.ROUNDED))

    # Left: Background
    bg_table = Table(title="Continuous Background Tasks", expand=True)
    bg_table.add_column("Game", style="cyan")
    bg_table.add_column("Status", style="magenta")
    bg_table.add_column("Latest Stat", style="green")
    
    for name, info in app_state["background"].items():
        bg_table.add_row(name, info["status"], info["last_stat"])
    
    layout["left"].update(Panel(bg_table, border_style="blue"))

    # Right: Sequential
    seq_table = Table(title="Sequential Task Queue (Looping)", expand=True)
    seq_table.add_column("Game", style="cyan")
    seq_table.add_column("Status", style="magenta")
    seq_table.add_column("Result", style="green")
    
    # History (last 10)
    for item in app_state["sequential"]["history"][-10:]:
        seq_table.add_row(item["name"], item["status"], item["result"])
    
    # Current
    curr = app_state["sequential"]["current"]
    if curr:
        seq_table.add_row(f"[bold yellow]{curr['name']}[/bold yellow]", "[bold blink yellow]SOLVING[/bold blink yellow]", curr["last_stat"])
    
    layout["right"].update(Panel(seq_table, border_style="green"))

    # Footer
    layout["footer"].update(Panel("Press [bold red]Ctrl+C[/bold red] to terminate all solvers. Dashboard refreshes every 0.25s.", box=box.ROUNDED))
    
    return layout

def main():
    global EMAIL, PASSWORD
    
    console.clear()
    console.print(Panel("[bold cyan]HYPNOS MASTER SOLVER INITIALIZATION[/bold cyan]", expand=False))
    
    if not EMAIL:
        EMAIL = Prompt.ask("[bold green]Enter Email[/bold green]")
    if not PASSWORD:
        PASSWORD = Prompt.ask("[bold green]Enter Password[/bold green]", password=True)
        
    if not EMAIL or not PASSWORD:
        console.print("[bold red]Credentials required. Exiting.[/bold red]")
        return

    # Start background threads for background games
    for game in SOLVERS["background"]:
        t = threading.Thread(target=run_solver_thread, args=(game["name"], game["path"], True), daemon=True)
        t.start()
        time.sleep(0.5)

    # Start a manager thread for sequential games (now looping!)
    def sequential_manager():
        while app_state["running"]:
            for game in SOLVERS["sequential"]:
                if not app_state["running"]: break
                run_solver_thread(game["name"], game["path"], False, game.get("args"))
                time.sleep(1)
            time.sleep(5) # Pause between full rounds

    t_seq = threading.Thread(target=sequential_manager, daemon=True)
    t_seq.start()

    # Dashboard Loop
    try:
        with Live(make_dashboard(), refresh_per_second=4, screen=True) as live:
            while True:
                live.update(make_dashboard())
                time.sleep(0.25)
    except KeyboardInterrupt:
        app_state["running"] = False
        console.print("\n[bold red]Shutdown requested. Cleaning up...[/bold red]")
        # Force terminate all subprocesses
        for name, info in app_state["background"].items():
            if "process" in info:
                info["process"].terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
