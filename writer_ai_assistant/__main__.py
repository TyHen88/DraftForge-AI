from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="writer-ai-assistant")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("run", help="Run the Telegram bot (polling).")
    sub.add_parser("serve", help="Run the Mini App HTTP API only (FastAPI/uvicorn).")
    sub.add_parser("web", help="Run the API + polling bot together in one process (Railway).")
    sub.add_parser("doctor", help="Print config and test OpenAI-compatible API connectivity.")

    args = parser.parse_args()

    if args.cmd in (None, "run"):
        from writer_ai_assistant.telegram_bot import run_polling

        run_polling()
        return

    if args.cmd == "serve":
        from writer_ai_assistant.serve import run_api

        run_api()
        return

    if args.cmd == "web":
        from writer_ai_assistant.serve import run_web

        run_web()
        return

    if args.cmd == "doctor":
        from writer_ai_assistant.doctor import run_doctor

        run_doctor()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
