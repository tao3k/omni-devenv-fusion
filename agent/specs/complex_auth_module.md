Spec: Complex Auth Module

> **Status**: Approved
> **Complexity**: L2
> **Owner**: @omni-coder

## 1. Context & Goal (Why)

_Building a centralized authentication module for the Omni-DevEnv project to provide secure, reusable auth primitives across MCP servers and CLI tools._

- **Goal**: Create a `complex_auth_module` that handles authentication flows, credential management, and session lifecycle for the orchestrator and coder MCP servers.
- **User Story**: As a developer, I want a unified authentication module so that I can implement secure access control without reinventing auth patterns for each component.
- **Pain Point**: Currently, authentication logic is scattered across MCP server implementations, leading to inconsistent security practices and duplicated code.

## 2. Architecture & Interface (What)

_Defines the authentication module contract and its integration points with the broader system._

### 2.1 File Changes

- `mcp-server/auth.py`: Created (main auth module with core primitives)
- `mcp-server/auth/token_handler.py`: Created (JWT token creation/validation)
- `mcp-server/auth/credential_store.py`: Created (encrypted credential storage)
- `mcp-server/orchestrator.py`: Modified (integrate auth middleware)
- `mcp-server/coder.py`: Modified (integrate auth middleware)

### 2.2 Data Structures / Schema

```python
class AuthConfig(BaseModel):
    """Configuration for the authentication module."""
    secret_key: str
    token_expiry_seconds: int = 3600
    algorithm: str = "HS256"
    credential_storage_path: str

class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: str  # Subject (user ID)
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    scopes: list[str]  # Permission scopes

class AuthResult(BaseModel):
    """Return type for authentication operations."""
    success: bool
    token: Optional[str]
    error: Optional[str]
    expires_at: Optional[int]

class Credential(BaseModel):
    """Schema for stored credentials."""
    identifier: str
    encrypted_data: bytes
    created_at: int
    updated_at: int
```

### 2.3 API Signatures (Pseudo-code)

```python
class AuthModule:
    """Centralized authentication module for Omni-DevEnv."""

    def __init__(self, config: AuthConfig) -> None:
        """Initialize auth module with configuration."""
        self.config = config
        self.token_handler = TokenHandler(config.secret_key, config.algorithm)
        self.credential_store = CredentialStore(config.credential_storage_path)

    async def authenticate(self, identifier: str, secret: str) -> AuthResult:
        """Authenticate a user with identifier and secret.

        Args:
            identifier: User identifier (username, API key, etc.)
            secret: Authentication secret (password, API key, etc.)

        Returns:
            AuthResult with success status and token if successful.
        """
        ...

    async def validate_token(self, token: str) -> Optional[TokenPayload]:
        """Validate a JWT token and return its payload.

        Args:
            token: JWT token string to validate.

        Returns:
            TokenPayload if valid, None if invalid/expired.
        """
        ...

    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh an expired token using a refresh token.

        Args:
            refresh_token: Valid refresh token.

        Returns:
            AuthResult with new access token if successful.
        """
        ...

    async def store_credential(self, identifier: str, data: bytes) -> None:
        """Store encrypted credential for an identifier.

        Args:
            identifier: Unique credential identifier.
            data: Raw credential data to encrypt and store.
        """
        ...

    async def get_credential(self, identifier: str) -> Optional[bytes]:
        """Retrieve and decrypt credential for an identifier.

        Args:
            identifier: Credential identifier.

        Returns:
            Decrypted credential data or None if not found.
        """
        ...

    def has_permission(self, payload: TokenPayload, required_scope: str) -> bool:
        """Check if token payload includes required permission scope.

        Args:
            payload: Validated token payload.
            required_scope: Required permission scope.

        Returns:
            True if scope is present, False otherwise.
        """
        ...
```

### 2.4 Integration Points

```python
# MCP Server Integration (orchestrator.py)
from mcp_server.auth import AuthModule, AuthConfig

auth_module = AuthModule(AuthConfig(
    secret_key=settings.auth_secret,
    token_expiry_seconds=7200,
    credential_storage_path=settings.credential_path
))

async def authenticated_tool(tool_func):
    """Decorator to enforce authentication on MCP tools."""
    async def wrapper(request):
        token = extract_bearer_token(request)
        payload = await auth_module.validate_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        if not auth_module.has_permission(payload, tool_func.required_scope):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return await tool_func(request)
    return wrapper
```

## 3. Implementation Plan (How)

1. [ ] **Create Auth Module Skeleton**: Establish `mcp-server/auth/` directory structure with `__init__.py`
2. [ ] **Implement TokenHandler**: JWT token creation, validation, and refresh logic
3. [ ] **Implement CredentialStore**: Encrypted storage using Fernet symmetric encryption
4. [ ] **Implement AuthModule**: Coordinator class tying together handlers and store
5. [ ] **Add Auth Middleware to MCP Servers**: Integrate authentication checks in orchestrator.py and coder.py
6. [ ] **Add CLI Integration**: Expose auth commands via `just auth-*` commands
7. [ ] **Update Documentation**: Add auth module docs to `docs/explanation/auth.md`

## 4. Verification Plan (Test)

_How do we know it works? Matches `agent/standards/feature-lifecycle.md` requirements._

**Note**: Per task requirements, tests are excluded from this implementation. This represents a compliance deviation from feature-lifecycle.md L2 standards which require unit tests.

- [ ] **Token Operations**: Manually verify JWT creation, validation, and refresh flow
- [ ] **Credential Storage**: Verify encrypted storage and retrieval with valid/invalid credentials
- [ ] **MCP Integration**: Verify auth middleware rejects unauthenticated requests
- [ ] **Permission Checking**: Verify scope-based access control works correctly
- [ ] **CLI Commands**: Verify `just auth-token` and related commands function

**Compliance Note**: This implementation does not include automated tests. Future iteration should add:

- Unit tests for TokenHandler (token creation/validation)
- Unit tests for CredentialStore (encryption/decryption)
- Unit tests for AuthModule (authentication flow)
-
