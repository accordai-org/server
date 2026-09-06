"""Vendor-neutral execution provider abstraction.

Execution providers give Accord an isolated environment in which an agent
can execute work. The rest of the application must depend only on the
interfaces and models defined here.

Concrete implementations (E2B, local development, etc.) belong in their
own provider modules and must never leak into the agent/runtime layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExecutionError(Exception):
    """Base exception for execution-provider failures."""


class ExecutionProviderError(ExecutionError):
    """Raised when an execution provider fails."""


class ExecutionConfigurationError(ExecutionError):
    """Raised when an execution provider is incorrectly configured."""


class ExecutionEnvironmentStatus(str, Enum):
    """Lifecycle state of an execution environment."""

    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class ExecutionEnvironment(BaseModel):
    """Provider-neutral representation of an isolated execution environment."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    provider: str = Field(
        description="Execution provider that owns this environment."
    )
    external_id: str = Field(
        description="Provider-specific environment identifier."
    )
    status: ExecutionEnvironmentStatus = Field(
        default=ExecutionEnvironmentStatus.CREATING
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionFile(BaseModel):
    """A file supplied to or produced by an execution."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        min_length=1,
        description="Path relative to the execution environment.",
    )
    content: bytes | None = Field(
        default=None,
        description="File contents when materialized locally.",
    )
    content_type: str | None = None


class ExecutionRequest(BaseModel):
    """Configuration required to create an isolated environment."""

    model_config = ConfigDict(extra="forbid")

    image: str | None = Field(
        default=None,
        description="Runtime/container image requested by the caller.",
    )
    working_directory: str = Field(default="/workspace")
    environment: dict[str, str] = Field(default_factory=dict)
    files: list[ExecutionFile] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionTask(BaseModel):
    """One command/task to execute inside an environment."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(
        min_length=1,
        description="Executable or shell command to run.",
    )
    args: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Provider-neutral result of an execution task."""

    model_config = ConfigDict(extra="forbid")

    execution_id: UUID = Field(default_factory=uuid4)
    environment_id: UUID
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionEventKind(str, Enum):
    """Kinds of events emitted while an execution is running."""

    STARTED = "started"
    STDOUT = "stdout"
    STDERR = "stderr"
    STATUS = "status"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionEvent(BaseModel):
    """One incremental event emitted by an execution provider."""

    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    environment_id: UUID
    kind: ExecutionEventKind
    data: str | dict[str, Any] | None = None
    sequence: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionArtifact(BaseModel):
    """A file/artifact produced by an execution."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    environment_id: UUID
    path: str
    size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = None
    content: bytes | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionHandle(BaseModel):
    """Handle returned immediately after an execution starts."""

    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    environment_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)

class ExecutionProvider(ABC):
    """Abstract interface implemented by every execution backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider identifier."""

    @abstractmethod
    async def create_environment(
        self,
        request: ExecutionRequest,
    ) -> ExecutionEnvironment:
        """Create and prepare an isolated execution environment."""

    @abstractmethod
    async def start_execution(
        self,
        environment: ExecutionEnvironment,
        task: ExecutionTask,
    ) -> ExecutionHandle:
        """Start execution and return its handle immediately."""

    @abstractmethod
    async def wait_execution(
        self,
        handle: ExecutionHandle,
    ) -> ExecutionResult:
        """Wait for a started execution to finish."""

    async def execute(
        self,
        environment: ExecutionEnvironment,
        task: ExecutionTask,
    ) -> ExecutionResult:
        """Start and wait for an execution."""

        handle = await self.start_execution(
            environment,
            task,
        )

        return await self.wait_execution(handle)

    @abstractmethod
    async def stream_events(
        self,
        handle: ExecutionHandle,
    ) -> AsyncIterator[ExecutionEvent]:
        """Stream events for a started execution."""

    @abstractmethod
    async def collect_artifacts(
        self,
        environment: ExecutionEnvironment,
    ) -> list[ExecutionArtifact]:
        """Collect files/artifacts produced by the environment."""

    @abstractmethod
    async def destroy_environment(
        self,
        environment: ExecutionEnvironment,
    ) -> None:
        """Destroy the isolated environment and release its resources."""

    async def close(self) -> None:
        """Release provider-level resources."""