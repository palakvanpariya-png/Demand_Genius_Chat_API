# app/config/logging_config.py
"""
Logging configuration for the advisory system
"""

import os
from loguru import logger
import sys
from pathlib import Path

def setup_logging():
    """
    Configure loguru for file and console logging
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Remove default handler
    logger.remove()
    
    # Console handler with color formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # File handler - Daily rotation
    logger.add(
        "logs/advisory_system_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention="30 days",
        level="DEBUG",
        compression="zip"  # Compress old logs to save space
    )
    
    # Error-specific log file
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="1 day",
        retention="60 days",  # Keep errors longer
        compression="zip"
    )
    
    # Query parsing specific logs (for debugging)
    logger.add(
        "logs/query_parsing_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        filter=lambda record: "query_parser" in record["name"] or "advisory" in record["name"],
        rotation="1 day",
        retention="14 days",
        level="DEBUG"
    )
    
    logger.info("Logging system initialized successfully")
    return logger


def get_logger(name: str = None):
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


# Configuration for different environments
class LoggingConfig:
    """Environment-specific logging configurations"""
    
    DEVELOPMENT = {
        "console_level": "DEBUG",
        "file_level": "DEBUG",
        "retention_days": 7,
        "enable_query_logs": True
    }
    
    PRODUCTION = {
        "console_level": "INFO", 
        "file_level": "INFO",
        "retention_days": 30,
        "enable_query_logs": False
    }
    
    TESTING = {
        "console_level": "WARNING",
        "file_level": "DEBUG", 
        "retention_days": 1,
        "enable_query_logs": True
    }


def setup_environment_logging(env: str = "development"):
    """
    Setup logging based on environment
    
    Args:
        env: Environment name (development, production, testing)
    """
    config_map = {
        "development": LoggingConfig.DEVELOPMENT,
        "production": LoggingConfig.PRODUCTION,
        "testing": LoggingConfig.TESTING
    }
    
    config = config_map.get(env.lower(), LoggingConfig.DEVELOPMENT)
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Remove default handler
    logger.remove()
    
    # Console handler
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level=config["console_level"]
    )
    
    # Main application log
    logger.add(
        f"logs/app_{env}_{'{time:YYYY-MM-DD}'}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention=f"{config['retention_days']} days",
        level=config["file_level"],
        compression="zip"
    )
    
    # Query-specific logs (if enabled)
    if config["enable_query_logs"]:
        logger.add(
            f"logs/queries_{env}_{'{time:YYYY-MM-DD}'}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
            filter=lambda record: any(keyword in record["message"].lower() 
                                    for keyword in ["query", "semantic", "distribution", "advisory"]),
            rotation="1 day",
            retention="7 days"
        )
    
    logger.info(f"Logging configured for {env} environment")


# Utility functions for specific logging needs
def log_query_performance(query: str, operation: str, duration: float, results_count: int):
    """Log query performance metrics"""
    logger.info(f"PERFORMANCE | Query: '{query[:50]}...' | Operation: {operation} | Duration: {duration:.3f}s | Results: {results_count}")


def log_api_call(service: str, tokens_in: int, tokens_out: int, cost: float):
    """Log API usage for monitoring"""
    logger.info(f"API_USAGE | Service: {service} | Tokens: {tokens_in}→{tokens_out} | Cost: ${cost:.4f}")


def log_user_interaction(tenant_id: str, query: str, operation: str, confidence: str):
    """Log user interactions for analytics"""
    logger.info(f"USER_INTERACTION | Tenant: {tenant_id} | Query: '{query[:30]}...' | Op: {operation} | Confidence: {confidence}")


# Example integration with existing services
class LoggerMixin:
    """Mixin to add consistent logging to service classes"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def log_service_start(self, method_name: str, **kwargs):
        """Log service method start"""
        self.logger.debug(f"Starting {method_name} with args: {kwargs}")
    
    def log_service_success(self, method_name: str, result_preview: str = None):
        """Log service method success"""
        if result_preview:
            self.logger.info(f"{method_name} completed successfully. Preview: {result_preview}")
        else:
            self.logger.info(f"{method_name} completed successfully")
    
    def log_service_error(self, method_name: str, error: Exception):
        """Log service method error"""
        self.logger.error(f"{method_name} failed: {error}")