"""Shared utilities used across the application."""
from .logging import configure_logging, get_logger, bind_context, clear_context
from .storage import redis, get_redis, RedisClient
from .llm import (
    embed_text,
    embed_batch_text,
    get_llm_answer,
    get_llm_client,
    get_conversation_context,
    save_conversation_context,
    clear_conversation_context,
    get_user_context,
)

__all__ = [
    # logging
    'configure_logging',
    'get_logger',
    'bind_context',
    'clear_context',
    # cache
    'redis',
    'get_redis',
    'RedisClient',
    # llm
    'embed_text',
    'embed_batch_text',
    'get_llm_answer',
    'get_llm_client',
    'get_conversation_context',
    'save_conversation_context',
    'clear_conversation_context',
    'get_user_context',
]
