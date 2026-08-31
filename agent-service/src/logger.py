"""
Structured logging via structlog.
- Local/test: pretty console output
- If LOG_SERVICE_URL is set: also ships logs to the external endpoint via httpx
"""
import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", log_service_url: str = "") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    if log_service_url:
        _attach_remote_handler(log_service_url, level)


def _attach_remote_handler(url: str, level: int) -> None:
    """Ship logs to an external HTTP endpoint (fire-and-forget)."""
    import httpx

    class RemoteHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                httpx.post(
                    url,
                    json={
                        "level": record.levelname,
                        "message": self.format(record),
                        "logger": record.name,
                    },
                    timeout=2,
                )
            except Exception:
                pass  # never crash the app over logging

    handler = RemoteHandler(level)
    logging.getLogger().addHandler(handler)


def get_logger(name: str = __name__):
    return structlog.get_logger(name)
