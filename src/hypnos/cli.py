import argparse
import sys
from hypnos.lib import setup_logger

# Lazy imports to avoid loading all dependencies at start
# We import them inside the handler functions

def handle_wordle(args):
    if args.mode == "train":
        from hypnos.wordle import train
        train.main()
    else:
        from hypnos.wordle import solve
        solve.main()

def handle_breakout(args):
    if args.mode == "train":
        from hypnos.breakout import train
        train.main()
    else:
        from hypnos.breakout import solve
        solve.main()

def handle_snake(args):
    if args.mode == "train":
        from hypnos.snake import train
        train.main()
    else:
        from hypnos.snake import solve
        solve.main()

def handle_trivia(args):
    from hypnos.trivia import solve
    if args.theme:
        solve.solve_theme(args.theme)
    else:
        logger = setup_logger("hypnos_cli")
        logger.info("No theme specified. Solving all themes...")
        for theme in solve.THEMES:
            solve.solve_theme(theme)

def handle_2048(args):
    from hypnos.twothousandfortyeight import solve
    solve.main()

def main():
    parser = argparse.ArgumentParser(description="Hypnos 2026 Bot Suite")
    subparsers = parser.add_subparsers(dest="game", required=True, help="Game to play/solve")

    # Wordle
    p_wordle = subparsers.add_parser("wordle", help="Wordle solver")
    p_wordle.add_argument("mode", choices=["solve", "train"], nargs="?", default="solve", help="Operation mode")
    p_wordle.set_defaults(func=handle_wordle)

    # Breakout
    p_breakout = subparsers.add_parser("breakout", help="Breakout (Casse-Briques) bot")
    p_breakout.add_argument("mode", choices=["solve", "train"], nargs="?", default="solve", help="Operation mode")
    p_breakout.set_defaults(func=handle_breakout)

    # Snake
    p_snake = subparsers.add_parser("snake", help="Snake score submitter")
    p_snake.add_argument("mode", choices=["solve", "train"], nargs="?", default="solve", help="Operation mode")
    p_snake.set_defaults(func=handle_snake)

    # Trivia
    p_trivia = subparsers.add_parser("trivia", help="Trivia/Sporcle solver")
    p_trivia.add_argument("--theme", "-t", type=str.lower, help="Specific theme to solve (e.g. bde, clubs)")
    p_trivia.set_defaults(func=handle_trivia)

    # 2048
    p_2048 = subparsers.add_parser("2048", help="2048 Solver")
    p_2048.set_defaults(func=handle_2048)

    # Parse
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
