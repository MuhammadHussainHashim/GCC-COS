"""Start the calculator: python -m gcc_cos.web --db data/carbon.sqlite --port 8000"""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description="GCC carbon footprint calculator (read-only web server)")
    parser.add_argument("--db", default="data/carbon.sqlite", help="GCC SQLite database; opened read-only")
    parser.add_argument("--host", default="127.0.0.1", help="Address to listen on; keep 127.0.0.1 unless you add authentication")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    import uvicorn
    from .app import create_app
    print(f"GCC calculator: open http://{args.host}:{args.port}/ in your browser (database {args.db}, read-only). Press Ctrl+C to stop.")
    uvicorn.run(create_app(args.db), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
