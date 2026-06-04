# Core utilities for Amp

from pathlib import Path


def mcp_error(message: str, code: str = "error") -> dict:
    """Standard MCP error response format."""
    return {"error": message, "code": code}


def mcp_success(data: dict = None, message: str = "Success") -> dict:
    """Standard MCP success response format."""
    result = {"success": True, "message": message}
    if data:
        result.update(data)
    return result


def validate_input(text: str, field_name: str, max_length: int = 200) -> str:
    """Validate and sanitize user input."""
    if not text or not text.strip():
        raise ValueError(f"{field_name} cannot be empty")
    text = text.strip()
    # Strip control characters
    text = ''.join(c for c in text if c.isprintable() or c in '\n\t')
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length} characters")
    return text


def validate_vault_path(path: Path, vault_root: Path) -> Path:
    """Validate that a resolved path stays within the vault root.

    Prevents path traversal attacks (e.g., ../../etc/passwd).
    Returns the resolved path if safe, raises ValueError otherwise.
    """
    resolved = path.resolve()
    vault_resolved = vault_root.resolve()
    if not resolved.is_relative_to(vault_resolved):
        raise ValueError(f"Path escapes vault boundary: {path}")
    return resolved
