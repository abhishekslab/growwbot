"""
Centralized logging configuration for production debugging.

Provides structured logging with rotation, async queue support, and multiple handlers.
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Log directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s"


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            }:
                log_obj[key] = value

        return json.dumps(log_obj)


def setup_logging(level: str = "INFO", log_to_file: bool = True, log_to_console: bool = True, json_format: bool = False) -> logging.Logger:
    """
    Setup centralized logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Enable file logging with rotation
        log_to_console: Enable console logging
        json_format: Use JSON format for structured logging

    Returns:
        Root logger instance
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    formatter = JSONFormatter() if json_format else logging.Formatter(DETAILED_FORMAT)

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        # Main log file - rotates daily, keeps 7 days
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=LOG_DIR / "growwbot.log", when="midnight", interval=1, backupCount=7, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Error log file - rotates when 10MB, keeps 5 files
        error_handler = logging.handlers.RotatingFileHandler(
            filename=LOG_DIR / "growwbot.error.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class RequestIdFilter(logging.Filter):
    """Filter to add request_id to log records."""

    def __init__(self, request_id: str = None):
        super().__init__()
        self.request_id = request_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", self.request_id or "-")
        return True


def log_request(logger: logging.Logger, method: str, path: str, request_id: str, extra: Dict[str, Any] = None) -> None:
    """Log an incoming request."""
    extra = extra or {}
    extra.update({"method": method, "path": path, "request_id": request_id, "event": "request"})
    logger.info(f"Request {method} {path}", extra=extra)


def log_response(
    logger: logging.Logger, method: str, path: str, status_code: int, duration_ms: float, request_id: str, extra: Dict[str, Any] = None
) -> None:
    """Log an outgoing response."""
    extra = extra or {}
    extra.update(
        {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "request_id": request_id,
            "event": "response",
        }
    )

    log_level = logging.INFO if status_code < 400 else logging.WARNING
    logger.log(log_level, f"Response {method} {path} {status_code} in {duration_ms:.2f}ms", extra=extra)


def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None) -> None:
    """Log an error with context."""
    context = context or {}
    context.update({"error_type": type(error).__name__, "error_message": str(error), "event": "error"})
    logger.exception(f"Error: {error}", extra=context)


# Initialize logging on import
log_level = os.getenv("LOG_LEVEL", "INFO")
logger = setup_logging(level=log_level, log_to_file=True, log_to_console=True, json_format=False)
