# Pharma Agent - API Client SDKs & Reference

## Table of Contents
1. [API Overview](#api-overview)
2. [Python SDK](#python-sdk)
3. [TypeScript/JavaScript SDK](#typescriptjavascript-sdk)
4. [Go SDK](#go-sdk)
5. [Postman Collection](#postman-collection)
6. [OpenAPI/Swagger](#openapyswagger)
7. [WebSocket Support](#websocket-support)
8. [Error Handling](#error-handling)
9. [Rate Limiting](#rate-limiting)
10. [Authentication Patterns](#authentication-patterns)

---

## API Overview

### Base URL

| Environment | URL |
|-------------|-----|
| **Development** | http://localhost:8000 |
| **Staging** | https://staging-api.pharma.example.com |
| **Production** | https://api.pharma.example.com |

### API Response Format

All responses follow this structure:

```json
{
  "status": "success|error|processing",
  "data": {},
  "error": null,
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_1234567890"
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Successful request |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Unexpected error |
| 503 | Service Unavailable | Maintenance mode |

---

## Python SDK

### Installation

```bash
# Via pip
pip install pharma-agent-sdk

# Via poetry
poetry add pharma-agent-sdk

# From source
git clone https://github.com/youorg/pharma-agent-sdk-python.git
pip install -e pharma-agent-sdk-python/
```

### Complete Python SDK Implementation

**File: `pharma_sdk/__init__.py`**

```python
"""
Pharma Agent Python SDK
Enterprise-grade client for pharmaceutical compliance automation
"""

__version__ = "1.0.0"
__author__ = "Your Organization"

from .client import PharmaClient
from .models import Token, User, ComplianceAudit, AuditResponse
from .exceptions import PharmaError, AuthenticationError, ValidationError

__all__ = [
    "PharmaClient",
    "Token",
    "User",
    "ComplianceAudit",
    "AuditResponse",
    "PharmaError",
    "AuthenticationError",
    "ValidationError",
]
```

**File: `pharma_sdk/models.py`**

```python
"""Data models for Pharma Agent API"""

from typing import Optional, List, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json


class AuditStatus(Enum):
    """Compliance audit status"""
    PASSED = "Passed"
    FAILED = "Failed"
    PENDING = "Pending"
    REVIEW_REQUIRED = "ReviewRequired"


@dataclass
class Token:
    """JWT authentication token"""
    access_token: str
    token_type: str
    expires_in: int = 3600

    def is_valid(self) -> bool:
        return bool(self.access_token and self.token_type == "bearer")


@dataclass
class User:
    """Authenticated user"""
    username: str
    team: str
    is_admin: bool = False

    def __repr__(self) -> str:
        return f"<User username={self.username} team={self.team}>"


@dataclass
class ComplianceAudit:
    """Compliance audit record"""
    id: int
    team: str
    metric: str
    score: int
    status: str
    date: str
    details: Optional[dict] = None

    def __repr__(self) -> str:
        return f"<ComplianceAudit id={self.id} metric={self.metric} score={self.score}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team": self.team,
            "metric": self.metric,
            "score": self.score,
            "status": self.status,
            "date": self.date,
            "details": self.details
        }


@dataclass
class AuditResponse:
    """API response containing audit data"""
    team: str
    audits: List[ComplianceAudit]

    @classmethod
    def from_dict(cls, data: dict) -> "AuditResponse":
        audits = [ComplianceAudit(**audit) for audit in data.get("audits", [])]
        return cls(team=data["team"], audits=audits)

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "audits": [audit.to_dict() for audit in self.audits]
        }
```

**File: `pharma_sdk/exceptions.py`**

```python
"""Custom exceptions for Pharma Agent SDK"""


class PharmaError(Exception):
    """Base exception for Pharma Agent SDK"""
    pass


class AuthenticationError(PharmaError):
    """Raised when authentication fails"""
    pass


class ValidationError(PharmaError):
    """Raised when request validation fails"""
    pass


class NotFoundError(PharmaError):
    """Raised when resource is not found"""
    pass


class RateLimitError(PharmaError):
    """Raised when rate limit is exceeded"""
    pass


class ServerError(PharmaError):
    """Raised when server returns 5xx error"""
    pass
```

**File: `pharma_sdk/client.py`**

```python
"""Main Pharma Agent API client"""

import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
import logging
from .models import Token, User, ComplianceAudit, AuditResponse
from .exceptions import (
    AuthenticationError,
    ValidationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    PharmaError
)

logger = logging.getLogger(__name__)


class PharmaClient:
    """
    Python client for Pharma Agent API
    
    Example:
        client = PharmaClient(
            base_url="http://localhost:8000",
            username="dr_smith",
            password="password123"
        )
        audits = client.get_audits()
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True
    ):
        """
        Initialize Pharma Agent client

        Args:
            base_url: API base URL
            username: Username for authentication
            password: Password for authentication
            token: Pre-existing JWT token
            timeout: Request timeout in seconds
            verify_ssl: Verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self._token: Optional[Token] = None
        self._user: Optional[User] = None

        # Authenticate if credentials provided
        if token:
            self._token = Token(access_token=token, token_type="bearer")
            self._set_auth_header()
            logger.info("Initialized with provided token")
        elif username and password:
            self.login(username, password)
        else:
            logger.warning("No credentials provided. Unauthenticated requests only.")

    def _set_auth_header(self) -> None:
        """Set Authorization header in session"""
        if self._token:
            self.session.headers.update({
                "Authorization": f"{self._token.token_type} {self._token.access_token}"
            })

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base_url)
            data: Request body data
            params: Query parameters
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response JSON as dictionary

        Raises:
            AuthenticationError: If auth fails
            ValidationError: If input invalid
            NotFoundError: If resource not found
            RateLimitError: If rate limited
            ServerError: If server error
        """
        url = urljoin(self.base_url, endpoint)

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                    **kwargs
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url,
                    data=data,
                    params=params,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                    **kwargs
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            # Handle errors
            if response.status_code == 401:
                raise AuthenticationError("Authentication failed. Check credentials.")
            elif response.status_code == 400:
                raise ValidationError(f"Validation error: {response.text}")
            elif response.status_code == 404:
                raise NotFoundError(f"Resource not found: {endpoint}")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Try again later.")
            elif response.status_code >= 500:
                raise ServerError(f"Server error: {response.status_code}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise PharmaError(f"Request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise PharmaError(f"Connection error: {str(e)}")

    # Authentication Methods

    def login(self, username: str, password: str) -> Token:
        """
        Authenticate and obtain JWT token

        Args:
            username: User's username
            password: User's password

        Returns:
            Token object

        Raises:
            AuthenticationError: If credentials invalid
        """
        response = self._request(
            "POST",
            "/token",
            data={"username": username, "password": password}
        )

        self._token = Token(
            access_token=response["access_token"],
            token_type=response.get("token_type", "bearer"),
            expires_in=response.get("expires_in", 3600)
        )
        self._set_auth_header()
        logger.info(f"Successfully logged in as {username}")
        return self._token

    def logout(self) -> None:
        """Clear authentication"""
        self._token = None
        self._user = None
        self.session.headers.pop("Authorization", None)
        logger.info("Logged out")

    # Data Access Methods

    def get_audits(self, limit: int = 100, offset: int = 0) -> AuditResponse:
        """
        Retrieve compliance audits for current user's team

        Args:
            limit: Maximum results (default: 100)
            offset: Result offset for pagination

        Returns:
            AuditResponse containing audits

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If parameters invalid
        """
        if not self._token:
            raise AuthenticationError("Not authenticated. Call login() first.")

        response = self._request(
            "GET",
            "/compliance/audits",
            params={"limit": limit, "offset": offset}
        )

        return AuditResponse.from_dict(response)

    def get_audit(self, audit_id: int) -> ComplianceAudit:
        """
        Retrieve specific audit by ID

        Args:
            audit_id: Audit ID

        Returns:
            ComplianceAudit object

        Raises:
            NotFoundError: If audit not found
        """
        response = self._request("GET", f"/compliance/audits/{audit_id}")
        return ComplianceAudit(**response)

    def create_audit(
        self,
        metric: str,
        score: int,
        status: str = "Passed",
        details: Optional[dict] = None
    ) -> ComplianceAudit:
        """
        Create new compliance audit

        Args:
            metric: Metric name
            score: Score (0-100)
            status: Audit status
            details: Additional details

        Returns:
            Created ComplianceAudit

        Raises:
            ValidationError: If input invalid
        """
        if not 0 <= score <= 100:
            raise ValidationError("Score must be between 0 and 100")

        data = {
            "metric": metric,
            "score": score,
            "status": status,
            "details": details
        }

        response = self._request("POST", "/compliance/audits", data=data)
        return ComplianceAudit(**response)

    # Utility Methods

    def health_check(self) -> bool:
        """
        Check if API is healthy

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._request("GET", "/health")
            return response.get("status") == "healthy"
        except PharmaError:
            return False

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.session.close()
```

### Python SDK Usage Examples

```python
# Example 1: Basic Usage
from pharma_sdk import PharmaClient

client = PharmaClient(
    base_url="http://localhost:8000",
    username="dr_smith",
    password="password123"
)

# Get audits
audits = client.get_audits()
print(f"Team: {audits.team}")
print(f"Audits: {len(audits.audits)}")

for audit in audits.audits:
    print(f"  - {audit.metric}: {audit.score}% ({audit.status})")
```

```python
# Example 2: Context Manager
with PharmaClient(base_url="http://localhost:8000") as client:
    client.login("dr_smith", "password123")
    audits = client.get_audits(limit=50)
    # Session auto-closes
```

```python
# Example 3: Error Handling
from pharma_sdk import PharmaClient
from pharma_sdk.exceptions import AuthenticationError, ValidationError

client = PharmaClient(base_url="http://localhost:8000")

try:
    client.login("invalid_user", "wrong_password")
except AuthenticationError as e:
    print(f"Login failed: {e}")

try:
    audit = client.create_audit("Test", score=150)  # Invalid
except ValidationError as e:
    print(f"Validation error: {e}")
```

```python
# Example 4: Batch Operations
from pharma_sdk import PharmaClient

client = PharmaClient(
    base_url="http://localhost:8000",
    token="<JWT_TOKEN>"
)

# Create multiple audits
metrics = ["Data Privacy", "Lab Safety", "Clinical Trial Management"]
for metric in metrics:
    audit = client.create_audit(metric=metric, score=90, status="Passed")
    print(f"Created audit: {audit.id}")
```

---

## TypeScript/JavaScript SDK

### Installation

```bash
# Via npm
npm install @pharma-agent/sdk

# Via yarn
yarn add @pharma-agent/sdk

# Via pnpm
pnpm add @pharma-agent/sdk
```

### Complete TypeScript SDK

**File: `src/index.ts`**

```typescript
export { PharmaClient } from './client';
export * from './types';
export * from './exceptions';
```

**File: `src/types.ts`**

```typescript
/**
 * TypeScript types for Pharma Agent API
 */

export interface Token {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface User {
  username: string;
  team: string;
  is_admin?: boolean;
}

export enum AuditStatus {
  PASSED = 'Passed',
  FAILED = 'Failed',
  PENDING = 'Pending',
  REVIEW_REQUIRED = 'ReviewRequired',
}

export interface ComplianceAudit {
  id: number;
  team: string;
  metric: string;
  score: number;
  status: string;
  date: string;
  details?: Record<string, any>;
}

export interface AuditResponse {
  team: string;
  audits: ComplianceAudit[];
}

export interface ApiResponse<T = any> {
  status: 'success' | 'error' | 'processing';
  data?: T;
  error?: string;
  timestamp: string;
  request_id: string;
}

export interface PharmaClientConfig {
  baseUrl?: string;
  username?: string;
  password?: string;
  token?: string;
  timeout?: number;
  verifySsl?: boolean;
}
```

**File: `src/exceptions.ts`**

```typescript
/**
 * Custom exceptions for Pharma Agent SDK
 */

export class PharmaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PharmaError';
  }
}

export class AuthenticationError extends PharmaError {
  constructor(message: string = 'Authentication failed') {
    super(message);
    this.name = 'AuthenticationError';
  }
}

export class ValidationError extends PharmaError {
  constructor(message: string = 'Validation failed') {
    super(message);
    this.name = 'ValidationError';
  }
}

export class NotFoundError extends PharmaError {
  constructor(message: string = 'Resource not found') {
    super(message);
    this.name = 'NotFoundError';
  }
}

export class RateLimitError extends PharmaError {
  constructor(message: string = 'Rate limit exceeded') {
    super(message);
    this.name = 'RateLimitError';
  }
}

export class ServerError extends PharmaError {
  constructor(message: string = 'Server error') {
    super(message);
    this.name = 'ServerError';
  }
}
```

**File: `src/client.ts`**

```typescript
/**
 * Main Pharma Agent API client for TypeScript/JavaScript
 */

import axios, {
  AxiosInstance,
  AxiosResponse,
  AxiosError,
} from 'axios';
import {
  Token,
  User,
  ComplianceAudit,
  AuditResponse,
  PharmaClientConfig,
  ApiResponse,
} from './types';
import {
  PharmaError,
  AuthenticationError,
  ValidationError,
  NotFoundError,
  RateLimitError,
  ServerError,
} from './exceptions';

const logger = {
  info: (msg: string) => console.log(`[INFO] ${msg}`),
  warn: (msg: string) => console.warn(`[WARN] ${msg}`),
  error: (msg: string) => console.error(`[ERROR] ${msg}`),
};

export class PharmaClient {
  private baseUrl: string;
  private timeout: number;
  private axiosInstance: AxiosInstance;
  private token: Token | null = null;
  private user: User | null = null;

  /**
   * Initialize Pharma Agent client
   *
   * @param config Client configuration
   *
   * @example
   * const client = new PharmaClient({
   *   baseUrl: 'http://localhost:8000',
   *   username: 'dr_smith',
   *   password: 'password123'
   * });
   */
  constructor(config: PharmaClientConfig = {}) {
    this.baseUrl = config.baseUrl || 'http://localhost:8000';
    this.timeout = config.timeout || 30000;

    this.axiosInstance = axios.create({
      baseURL: this.baseUrl.replace(/\/$/, ''),
      timeout: this.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      (error) => this.handleAxiosError(error)
    );

    // Authenticate if credentials provided
    if (config.token) {
      this.token = {
        access_token: config.token,
        token_type: 'bearer',
      };
      this.setAuthHeader();
      logger.info('Initialized with provided token');
    } else if (config.username && config.password) {
      this.login(config.username, config.password);
    } else {
      logger.warn('No credentials provided. Unauthenticated requests only.');
    }
  }

  private setAuthHeader(): void {
    if (this.token) {
      this.axiosInstance.defaults.headers.common['Authorization'] =
        `${this.token.token_type} ${this.token.access_token}`;
    }
  }

  private handleAxiosError(error: AxiosError): Promise<never> {
    const status = error.response?.status;
    const data = error.response?.data as any;

    switch (status) {
      case 401:
        throw new AuthenticationError(
          data?.error || 'Authentication failed'
        );
      case 400:
        throw new ValidationError(
          data?.error || 'Validation error'
        );
      case 404:
        throw new NotFoundError(
          data?.error || 'Resource not found'
        );
      case 429:
        throw new RateLimitError(
          data?.error || 'Rate limit exceeded'
        );
      case 500:
      case 502:
      case 503:
      case 504:
        throw new ServerError(
          data?.error || `Server error: ${status}`
        );
      default:
        throw new PharmaError(error.message || 'Unknown error');
    }
  }

  /**
   * Authenticate and obtain JWT token
   */
  async login(username: string, password: string): Promise<Token> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await this.axiosInstance.post<Token>(
      '/token',
      formData,
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }
    );

    this.token = response.data;
    this.setAuthHeader();
    logger.info(`Successfully logged in as ${username}`);
    return this.token;
  }

  /**
   * Clear authentication
   */
  logout(): void {
    this.token = null;
    this.user = null;
    delete this.axiosInstance.defaults.headers.common['Authorization'];
    logger.info('Logged out');
  }

  /**
   * Retrieve compliance audits for current user's team
   */
  async getAudits(limit: number = 100, offset: number = 0): Promise<AuditResponse> {
    if (!this.token) {
      throw new AuthenticationError('Not authenticated. Call login() first.');
    }

    const response = await this.axiosInstance.get<AuditResponse>(
      '/compliance/audits',
      { params: { limit, offset } }
    );

    return response.data;
  }

  /**
   * Retrieve specific audit by ID
   */
  async getAudit(auditId: number): Promise<ComplianceAudit> {
    const response = await this.axiosInstance.get<ComplianceAudit>(
      `/compliance/audits/${auditId}`
    );
    return response.data;
  }

  /**
   * Create new compliance audit
   */
  async createAudit(
    metric: string,
    score: number,
    status: string = 'Passed',
    details?: Record<string, any>
  ): Promise<ComplianceAudit> {
    if (score < 0 || score > 100) {
      throw new ValidationError('Score must be between 0 and 100');
    }

    const response = await this.axiosInstance.post<ComplianceAudit>(
      '/compliance/audits',
      { metric, score, status, details }
    );

    return response.data;
  }

  /**
   * Check if API is healthy
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.axiosInstance.get<{ status: string }>(
        '/health'
      );
      return response.data.status === 'healthy';
    } catch {
      return false;
    }
  }
}
```

### TypeScript SDK Usage Examples

```typescript
// Example 1: Basic Usage
import { PharmaClient } from '@pharma-agent/sdk';

const client = new PharmaClient({
  baseUrl: 'http://localhost:8000',
  username: 'dr_smith',
  password: 'password123',
});

(async () => {
  const audits = await client.getAudits();
  console.log(`Team: ${audits.team}`);
  console.log(`Total audits: ${audits.audits.length}`);

  audits.audits.forEach((audit) => {
    console.log(
      `  - ${audit.metric}: ${audit.score}% (${audit.status})`
    );
  });
})();
```

```typescript
// Example 2: Error Handling
import { PharmaClient, AuthenticationError, ValidationError } from '@pharma-agent/sdk';

const client = new PharmaClient({ baseUrl: 'http://localhost:8000' });

try {
  await client.login('invalid_user', 'wrong_password');
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Login failed:', error.message);
  }
}

try {
  await client.createAudit('Test', 150); // Invalid score
} catch (error) {
  if (error instanceof ValidationError) {
    console.error('Validation failed:', error.message);
  }
}
```

```typescript
// Example 3: React Hook
import { useEffect, useState } from 'react';
import { PharmaClient, AuditResponse } from '@pharma-agent/sdk';

function useAudits(token: string) {
  const [audits, setAudits] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const client = new PharmaClient({ baseUrl: 'http://localhost:8000', token });

    (async () => {
      try {
        const data = await client.getAudits();
        setAudits(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  return { audits, loading, error };
}

// Usage in component
function AuditList() {
  const { audits, loading, error } = useAudits('<JWT_TOKEN>');

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>{audits?.team}</h2>
      <ul>
        {audits?.audits.map((audit) => (
          <li key={audit.id}>
            {audit.metric}: {audit.score}% ({audit.status})
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Go SDK

### Installation

```bash
go get github.com/youorg/pharma-agent-sdk-go
```

### Complete Go SDK

**File: `pharma/types.go`**

```go
package pharma

import "time"

// Token represents JWT authentication token
type Token struct {
    AccessToken string `json:"access_token"`
    TokenType   string `json:"token_type"`
    ExpiresIn   int    `json:"expires_in"`
}

// User represents authenticated user
type User struct {
    Username string `json:"username"`
    Team     string `json:"team"`
    IsAdmin  bool   `json:"is_admin,omitempty"`
}

// ComplianceAudit represents a compliance audit record
type ComplianceAudit struct {
    ID      int            `json:"id"`
    Team    string         `json:"team"`
    Metric  string         `json:"metric"`
    Score   int            `json:"score"`
    Status  string         `json:"status"`
    Date    string         `json:"date"`
    Details map[string]any `json:"details,omitempty"`
}

// AuditResponse contains audit data for current user's team
type AuditResponse struct {
    Team   string               `json:"team"`
    Audits []ComplianceAudit `json:"audits"`
}

// APIResponse is the base API response
type APIResponse struct {
    Status    string    `json:"status"`
    Data      any       `json:"data"`
    Error     string    `json:"error"`
    Timestamp time.Time `json:"timestamp"`
    RequestID string    `json:"request_id"`
}
```

**File: `pharma/client.go`**

```go
package pharma

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "net/url"
    "time"
)

// Client is the Pharma Agent API client
type Client struct {
    baseURL    string
    httpClient *http.Client
    token      *Token
}

// Config holds client configuration
type Config struct {
    BaseURL   string
    Username  string
    Password  string
    Token     string
    Timeout   time.Duration
    VerifySSL bool
}

// NewClient creates a new Pharma Agent client
func NewClient(config Config) (*Client, error) {
    if config.BaseURL == "" {
        config.BaseURL = "http://localhost:8000"
    }
    if config.Timeout == 0 {
        config.Timeout = 30 * time.Second
    }

    client := &Client{
        baseURL: config.BaseURL,
        httpClient: &http.Client{
            Timeout: config.Timeout,
        },
    }

    // Authenticate if token provided
    if config.Token != "" {
        client.token = &Token{
            AccessToken: config.Token,
            TokenType:   "bearer",
        }
        return client, nil
    }

    // Authenticate with credentials
    if config.Username != "" && config.Password != "" {
        if err := client.Login(config.Username, config.Password); err != nil {
            return nil, err
        }
    }

    return client, nil
}

// Login authenticates and obtains JWT token
func (c *Client) Login(username, password string) error {
    data := url.Values{
        "username": {username},
        "password": {password},
    }

    req, err := http.NewRequest(
        "POST",
        fmt.Sprintf("%s/token", c.baseURL),
        bytes.NewBufferString(data.Encode()),
    )
    if err != nil {
        return fmt.Errorf("failed to create request: %w", err)
    }

    req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

    resp, err := c.httpClient.Do(req)
    if err != nil {
        return fmt.Errorf("login request failed: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("login failed with status %d", resp.StatusCode)
    }

    if err := json.NewDecoder(resp.Body).Decode(&c.token); err != nil {
        return fmt.Errorf("failed to decode token: %w", err)
    }

    return nil
}

// GetAudits retrieves compliance audits for current user's team
func (c *Client) GetAudits(limit, offset int) (*AuditResponse, error) {
    if c.token == nil {
        return nil, fmt.Errorf("not authenticated")
    }

    req, err := http.NewRequest(
        "GET",
        fmt.Sprintf("%s/compliance/audits", c.baseURL),
        nil,
    )
    if err != nil {
        return nil, fmt.Errorf("failed to create request: %w", err)
    }

    q := req.URL.Query()
    q.Add("limit", fmt.Sprintf("%d", limit))
    q.Add("offset", fmt.Sprintf("%d", offset))
    req.URL.RawQuery = q.Encode()

    c.setAuthHeader(req)

    resp, err := c.httpClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("request failed with status %d", resp.StatusCode)
    }

    var result AuditResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("failed to decode response: %w", err)
    }

    return &result, nil
}

// CreateAudit creates a new compliance audit
func (c *Client) CreateAudit(
    metric string,
    score int,
    status string,
    details map[string]any,
) (*ComplianceAudit, error) {
    if score < 0 || score > 100 {
        return nil, fmt.Errorf("score must be between 0 and 100")
    }

    body := map[string]any{
        "metric":  metric,
        "score":   score,
        "status":  status,
        "details": details,
    }

    jsonBody, err := json.Marshal(body)
    if err != nil {
        return nil, fmt.Errorf("failed to marshal body: %w", err)
    }

    req, err := http.NewRequest(
        "POST",
        fmt.Sprintf("%s/compliance/audits", c.baseURL),
        bytes.NewReader(jsonBody),
    )
    if err != nil {
        return nil, fmt.Errorf("failed to create request: %w", err)
    }

    req.Header.Set("Content-Type", "application/json")
    c.setAuthHeader(req)

    resp, err := c.httpClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
        body, _ := io.ReadAll(resp.Body)
        return nil, fmt.Errorf("request failed with status %d: %s", resp.StatusCode, string(body))
    }

    var audit ComplianceAudit
    if err := json.NewDecoder(resp.Body).Decode(&audit); err != nil {
        return nil, fmt.Errorf("failed to decode response: %w", err)
    }

    return &audit, nil
}

// HealthCheck verifies API is healthy
func (c *Client) HealthCheck() error {
    req, err := http.NewRequest("GET", fmt.Sprintf("%s/health", c.baseURL), nil)
    if err != nil {
        return err
    }

    resp, err := c.httpClient.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("health check failed: status %d", resp.StatusCode)
    }

    return nil
}

func (c *Client) setAuthHeader(req *http.Request) {
    if c.token != nil {
        req.Header.Set("Authorization", fmt.Sprintf("%s %s", c.token.TokenType, c.token.AccessToken))
    }
}
```

### Go SDK Usage Example

```go
package main

import (
    "fmt"
    "log"
    "pharma"
)

func main() {
    // Create client
    client, err := pharma.NewClient(pharma.Config{
        BaseURL:  "http://localhost:8000",
        Username: "dr_smith",
        Password: "password123",
    })
    if err != nil {
        log.Fatal(err)
    }

    // Get audits
    audits, err := client.GetAudits(100, 0)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Team: %s\n", audits.Team)
    fmt.Printf("Total audits: %d\n", len(audits.Audits))

    for _, audit := range audits.Audits {
        fmt.Printf("  - %s: %d%% (%s)\n", audit.Metric, audit.Score, audit.Status)
    }

    // Create new audit
    newAudit, err := client.CreateAudit(
        "Clinical Trial Monitoring",
        88,
        "Passed",
        nil,
    )
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Created audit: %d\n", newAudit.ID)
}
```

---

## Postman Collection

### Import Collection

**File: `Pharma_Agent_API.postman_collection.json`**

```json
{
  "info": {
    "name": "Pharma Agent API",
    "description": "API collection for Pharma Agent compliance automation",
    "version": "1.0.0"
  },
  "auth": {
    "type": "bearer",
    "bearer": [
      {
        "key": "token",
        "value": "{{token}}",
        "type": "string"
      }
    ]
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000",
      "type": "string"
    },
    {
      "key": "token",
      "value": "",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "Authentication",
      "item": [
        {
          "name": "Login",
          "event": [
            {
              "listen": "test",
              "script": {
                "exec": [
                  "if (pm.response.code === 200) {",
                  "  var jsonData = pm.response.json();",
                  "  pm.environment.set('token', jsonData.access_token);",
                  "  pm.test('Token saved to environment', function() {",
                  "    pm.expect(pm.environment.get('token')).to.not.be.empty;",
                  "  });",
                  "}"
                ]
              }
            }
          ],
          "request": {
            "method": "POST",
            "header": [],
            "body": {
              "mode": "urlencoded",
              "urlencoded": [
                {
                  "key": "username",
                  "value": "dr_smith",
                  "type": "text"
                },
                {
                  "key": "password",
                  "value": "password123",
                  "type": "text"
                }
              ]
            },
            "url": {
              "raw": "{{base_url}}/token",
              "host": ["{{base_url}}"],
              "path": ["token"]
            }
          }
        }
      ]
    },
    {
      "name": "Compliance Audits",
      "item": [
        {
          "name": "Get All Audits",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "{{base_url}}/compliance/audits?limit=100&offset=0",
              "host": ["{{base_url}}"],
              "path": ["compliance", "audits"],
              "query": [
                {
                  "key": "limit",
                  "value": "100"
                },
                {
                  "key": "offset",
                  "value": "0"
                }
              ]
            }
          }
        },
        {
          "name": "Get Audit by ID",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "{{base_url}}/compliance/audits/1",
              "host": ["{{base_url}}"],
              "path": ["compliance", "audits", "1"]
            }
          }
        },
        {
          "name": "Create Audit",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\"metric\": \"Data Privacy\", \"score\": 92, \"status\": \"Passed\", \"details\": null}"
            },
            "url": {
              "raw": "{{base_url}}/compliance/audits",
              "host": ["{{base_url}}"],
              "path": ["compliance", "audits"]
            }
          }
        }
      ]
    },
    {
      "name": "Health & Status",
      "item": [
        {
          "name": "Health Check",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "{{base_url}}/health",
              "host": ["{{base_url}}"],
              "path": ["health"]
            }
          }
        },
        {
          "name": "Readiness Check",
          "request": {
            "method": "GET",
            "header": [],
            "url": {
              "raw": "{{base_url}}/readiness",
              "host": ["{{base_url}}"],
              "path": ["readiness"]
            }
          }
        }
      ]
    }
  ]
}
```

### Using Postman Collection

```bash
# Import collection
1. Open Postman
2. Click "Import"
3. Upload "Pharma_Agent_API.postman_collection.json"

# Set environment variables
1. Click "Environments"
2. Create new environment "Pharma Local"
3. Set:
   - base_url: http://localhost:8000
   - token: (auto-populated after login)

# Test workflow
1. Run "Login" request → captures token
2. Run "Get All Audits" request → uses token
3. Run "Create Audit" request → creates new audit
```

---

## OpenAPI/Swagger

### Access Swagger UI

```
http://localhost:8000/docs
```

### Generate OpenAPI Schema

```bash
# Get OpenAPI schema
curl http://localhost:8000/openapi.json > openapi.json

# Generate client SDK from schema
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o generated-sdk/python

openapi-generator-cli generate \
  -i openapi.json \
  -g typescript-axios \
  -o generated-sdk/typescript
```

---

## WebSocket Support (Optional)

For real-time compliance updates, implement WebSocket:

```python
# WebSocket endpoint
@app.websocket("/ws/audits/{team}")
async def websocket_audits(websocket: WebSocket, team: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Process real-time data
            await websocket.send_json({"status": "received", "data": data})
    except WebSocketDisconnect:
        pass
```

---

## Error Handling

### Standard Error Response

```json
{
  "status": "error",
  "error": "Invalid authentication token",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_1234567890"
}
```

### Error Codes Reference

| Code | Message | Action |
|------|---------|--------|
| 401 | Invalid credentials | Check username/password |
| 401 | Token expired | Re-authenticate |
| 400 | Invalid score | Ensure score is 0-100 |
| 404 | Audit not found | Verify audit ID |
| 429 | Rate limit exceeded | Wait before retrying |

---

## Rate Limiting

### Implementation

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/compliance/audits")
@limiter.limit("100/minute")
async def get_audits(request: Request):
    pass
```

### Rate Limits

| Endpoint | Limit |
|----------|-------|
| GET /compliance/audits | 100/minute |
| POST /compliance/audits | 20/minute |
| POST /token | 5/minute |

---

## Authentication Patterns

### OAuth2 with Authorization Code Flow

```python
# Step 1: Redirect to authorization endpoint
# https://pharma.example.com/oauth/authorize?client_id=xxx&redirect_uri=xxx

# Step 2: User logs in and grants permission

# Step 3: Receive authorization code
# https://app.example.com/callback?code=xxx

# Step 4: Exchange code for token
curl -X POST https://pharma.example.com/oauth/token \
  -d "grant_type=authorization_code&code=xxx&client_id=xxx&client_secret=xxx"
```

### API Key Authentication (Alternative)

```python
# Option: Use API key instead of OAuth2
@app.get("/compliance/audits")
async def get_audits(x_api_key: str = Header(...)):
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Process request
```

---

## Conclusion

This SDK documentation provides client implementations in Python, TypeScript/JavaScript, and Go. Choose your preferred language and language-specific implementation for seamless integration with Pharma Agent APIs.

**SDK Features:**
- ✅ Full CRUD operations
- ✅ Automatic token management
- ✅ Error handling with custom exceptions
- ✅ Request/response validation
- ✅ Retry logic (configurable)
- ✅ Async support (where applicable)
- ✅ Type hints/static typing
- ✅ Comprehensive documentation

For more information, visit the respective SDK repositories or refer to the OpenAPI schema at `/openapi.json`.
