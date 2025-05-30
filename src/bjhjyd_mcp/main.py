#!/usr/bin/env python3
"""
Main entry point for the Beijing Car Quota Lottery MCP Server.

This script can be run directly to start the MCP server, or imported
to use the server programmatically.
"""

import argparse
import sys
from pathlib import Path

from .server.mcp_server import run_server
from .utils.logging_config import setup_logging


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Beijing Car Quota Lottery MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python -m bjhjyd_mcp.main

  # Run on custom host and port
  python -m bjhjyd_mcp.main --host 0.0.0.0 --port 8080

  # Enable debug logging
  python -m bjhjyd_mcp.main --log-level DEBUG

  # Use custom data directory
  python -m bjhjyd_mcp.main --data-dir /path/to/data
        """
    )
    
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory to store processed data (default: data)"
    )
    
    parser.add_argument(
        "--downloads-dir",
        type=Path,
        default=Path("downloads"),
        help="Directory to store downloaded PDFs (default: downloads)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Optional log file path"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(
        level=args.log_level,
        log_file=args.log_file
    )
    
    # Run the server
    try:
        run_server(
            host=args.host,
            port=args.port,
            data_dir=args.data_dir,
            downloads_dir=args.downloads_dir
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 