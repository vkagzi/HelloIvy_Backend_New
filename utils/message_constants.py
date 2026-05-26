"""
Shared constants for message types across all conversation modules.
Use these constants instead of hardcoded strings to ensure consistency.
"""

# Message type constants for database models and services
class MessageType:
    """Message type constants for conversation systems"""
    BOT = 'bot'
    USER = 'user'
    
    # Choices for Django model fields
    CHOICES = [
        (BOT, 'Bot'),
        (USER, 'User'),
    ]


# LangChain/AI role mapping (for internal processing)
class AIRole:
    """Role constants for AI/LangChain message processing"""
    ASSISTANT = 'assistant'  # Used in LangChain AIMessage conversion
    USER = 'user'
    SYSTEM = 'system'
