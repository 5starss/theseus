class RemoteWorkspaceError(RuntimeError):
    """Base error for Remote Workspace operations."""


class RemoteWorkspaceAuthenticationError(RemoteWorkspaceError):
    """Raised when SSH authentication cannot be configured."""


class RemoteWorkspaceConnectionError(RemoteWorkspaceError):
    """Raised when SSH connection creation fails."""


class RemoteWorkspaceCommandTimeoutError(RemoteWorkspaceError):
    """Raised when a remote command exceeds the configured timeout."""


class RemoteWorkspaceCommandError(RemoteWorkspaceError):
    """Raised when remote command execution cannot be completed."""


class RemoteWorkspacePathError(RemoteWorkspaceError):
    """Raised when a requested path escapes the configured base path."""
