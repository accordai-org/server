"""Shared enumerations for domain models."""

from enum import Enum


class AgentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class MemoryScope(str, Enum):
    AGENT = "agent"
    RUN = "run"
    USER = "user"
    GLOBAL = "global"


class MemoryKind(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    FACT = "fact"


class StrategyStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"


class ToolKind(str, Enum):
    FUNCTION = "function"
    API = "api"
    MCP = "mcp"
    BUILTIN = "builtin"
