import logging
from logging.config import dictConfig


DEFAULT_LOG_FORMAT = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'


def configure_logging(level: str = 'INFO') -> None:
    dictConfig(
        {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': DEFAULT_LOG_FORMAT,
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard',
                }
            },
            'root': {
                'handlers': ['console'],
                'level': level.upper(),
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
