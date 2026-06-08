[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 5.3 Authentication & Authorization

### Authentication

**OAuth 2.0 Flows**

OAuth 2.0 is a delegation framework -- it allows a user to grant a third-party application limited access to their resources without sharing their password. Different "flows" (grant types) are designed for different application types. Here is the architecture:

```
Authorization Code Flow (Server-Side Apps -- Most Secure)
=========================================================

+--------+                               +---------------+
|        |  (1) Authorization Request     |               |
|        |  (redirect to /authorize)      | Authorization |
| User   | -----------------------------> |    Server     |
| (via   |                               |  (Google,     |
| Browser|  (2) User logs in & consents   |   GitHub,     |
|  )     | <----------------------------> |   Auth0)      |
|        |                               |               |
|        |  (3) Redirect with auth code   |               |
|        | <----------------------------- |               |
+--------+                               +---------------+
    |                                          ^     |
    | (3) Auth code sent to                    |     |
    |     your server via redirect             |     |
    v                                          |     |
+--------+                                     |     |
|        |  (4) Exchange code for tokens       |     |
| Your   |  POST /token                        |     |
| Backend|  {code, client_secret, redirect_uri}|     |
| Server | ----------------------------------->|     |
|        |                                     |     |
|        |  (5) Receive access_token           |     |
|        |      + refresh_token                |     |
|        | <-----------------------------------|     |
|        |                                           |
|        |  (6) Use access_token to call APIs        |
|        | ----------------------------------------->|
+--------+                               Resource Server
```

```
Authorization Code + PKCE (SPAs & Mobile Apps)
==============================================

Same as above, but instead of a client_secret (which cannot be
safely stored in a browser/mobile app), the client:

1. Generates a random code_verifier
2. Derives code_challenge = SHA256(code_verifier)
3. Sends code_challenge with the authorization request
4. Sends code_verifier when exchanging the code for tokens
5. The server verifies SHA256(code_verifier) == code_challenge

This prevents authorization code interception attacks.
```

```
Client Credentials Flow (Machine-to-Machine)
=============================================

+--------+                               +---------------+
| Service|  POST /token                   | Authorization |
|   A    |  {client_id, client_secret,    |    Server     |
|        |   grant_type=client_credentials|               |
|        | -----------------------------> |               |
|        |                               |               |
|        |  access_token                  |               |
|        | <----------------------------- |               |
|        |                               +---------------+
|        |
|        |  Use access_token
|        | -----------------------------> Service B
+--------+
```

```
Device Code Flow (TVs, CLIs, IoT)
==================================

+--------+                               +---------------+
| Device |  POST /device/code            | Authorization |
|  (TV)  |  {client_id}                  |    Server     |
|        | -----------------------------> |               |
|        |                               |               |
|        |  {device_code, user_code,     |               |
|        |   verification_uri}           |               |
|        | <----------------------------- |               |
+--------+                               +---------------+
    |                                          ^
    | Display: "Go to https://example.com/device |
    |           Enter code: ABCD-1234"            |
    v                                             |
+--------+                                        |
| User   |  (visits URL, enters code, logs in)    |
| (Phone)| --------------------------------------->|
+--------+
    Meanwhile, Device polls POST /token {device_code}
    until the user completes login.
```

The Implicit flow (where the access token is returned directly in the URL fragment) is deprecated because it exposes the token in browser history and server logs. Always use Authorization Code + PKCE for browser-based apps.

FastAPI implementation of the Authorization Code flow:

```python
# oauth_example.py -- OAuth 2.0 Authorization Code Flow
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx, secrets

app = FastAPI()

# Configuration (in practice, use environment variables)
OAUTH_CONFIG = {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
    "redirect_uri": "http://localhost:8000/auth/callback",
    "scopes": "openid email profile",
}

# In-memory state store (use Redis in production)
_state_store = set()

@app.get("/auth/login")
def login():
    """Step 1: Redirect user to the authorization server."""
    state = secrets.token_urlsafe(32)
    _state_store.add(state)
    params = {
        "client_id": OAUTH_CONFIG["client_id"],
        "redirect_uri": OAUTH_CONFIG["redirect_uri"],
        "response_type": "code",
        "scope": OAUTH_CONFIG["scopes"],
        "state": state,
        "access_type": "offline",  # Request refresh token
    }
    url = OAUTH_CONFIG["authorize_url"] + "?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    return RedirectResponse(url)

@app.get("/auth/callback")
async def callback(code: str, state: str):
    """Step 3-5: Exchange authorization code for tokens."""
    if state not in _state_store:
        raise HTTPException(400, "Invalid state parameter")
    _state_store.discard(state)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            OAUTH_CONFIG["token_url"],
            data={
                "code": code,
                "client_id": OAUTH_CONFIG["client_id"],
                "client_secret": OAUTH_CONFIG["client_secret"],
                "redirect_uri": OAUTH_CONFIG["redirect_uri"],
                "grant_type": "authorization_code",
            },
        )
        tokens = token_response.json()

        # Fetch user info with the access token
        userinfo_response = await client.get(
            OAUTH_CONFIG["userinfo_url"],
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        user = userinfo_response.json()

    return {
        "message": "Login successful",
        "user": user,
        "access_token": tokens["access_token"],
    }
```

**Device Code Flow in Depth**

The Device Code flow (the diagram above) exists for clients that cannot present a usable browser or accept a redirect: smart TVs, CLIs (`gh auth login`, `az login`), and other input-constrained or headless devices. Typing a password on a TV remote is miserable and embedding a `client_secret` in a distributed binary is insecure, so the flow moves the actual login onto a *second, trusted device* (the user's phone or laptop) while the original device simply polls in the background.

The exchange has two phases. First the device asks the authorization server for a pair of codes:

```text
POST /device/code
client_id=cli_app&scope=openid+profile

HTTP/1.1 200 OK
{
  "device_code": "GmRhmhcxhwAzkoEqiMEg_DnyEysNkuNhszIySk9eS",
  "user_code": "WDJB-MJHT",
  "verification_uri": "https://example.com/device",
  "verification_uri_complete": "https://example.com/device?code=WDJB-MJHT",
  "expires_in": 900,
  "interval": 5
}
```

The device displays the short, human-typeable `user_code` and the `verification_uri` ("Go to example.com/device and enter WDJB-MJHT"), while it keeps the long, secret `device_code` to itself. The user opens that URL on their phone, authenticates normally, and approves the request. Meanwhile the device polls the token endpoint:

```python
# device_flow_poll.py -- the polling half of the device flow
import time, httpx

def poll_for_token(device_code: str, interval: int, token_url: str, client_id: str):
    while True:
        resp = httpx.post(token_url, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        })
        body = resp.json()

        if resp.status_code == 200:
            return body                      # success: access + refresh tokens
        error = body.get("error")
        if error == "authorization_pending":
            time.sleep(interval)             # user hasn't approved yet -- keep waiting
        elif error == "slow_down":
            interval += 5                    # server says we're polling too fast
            time.sleep(interval)
        elif error in ("expired_token", "access_denied"):
            raise RuntimeError(f"Device flow failed: {error}")
        else:
            raise RuntimeError(f"Unexpected error: {error}")
```

A typical run prints (illustrative):

```console
$ mycli login
To sign in, open https://example.com/device and enter code: WDJB-MJHT
Waiting for authorization...
[polling] authorization_pending
[polling] authorization_pending
[polling] slow_down            # backing off: 5s -> 10s
[polling] authorization_pending
Login successful. Tokens stored.
```

**How to read this output:** the device never sees the user's credentials -- it only ever holds the `device_code` and polls. The two non-error "errors" are the whole protocol: `authorization_pending` is the *normal* state while the user is still on their phone (you keep polling at `interval` seconds), and `slow_down` is the server throttling an over-eager client, which you must honor by *increasing* the interval, not ignoring it -- hammering the endpoint can get the client blocked. The poll loop is bounded by `expires_in` (here 900s); past that the server returns `expired_token` and the device must restart with a fresh `/device/code` request. This decoupling of "where you authenticate" from "where you use the token" is exactly why the flow needs no redirect URI and no client secret, which is the point to make in an interview.

**JWT (JSON Web Token)**

A JWT is a compact, URL-safe token consisting of three base64url-encoded parts separated by dots: `Header.Payload.Signature`.

```
Token structure:
================

eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoiYWxpY2VAZXhhbXBsZS5jb20iLCJyb2xlcyI6WyJ1c2VyIiwiYWRtaW4iXSwiaWF0IjoxNzExMzI0ODAwLCJleHAiOjE3MTEzMjg0MDAsImlzcyI6Imh0dHBzOi8vYXV0aC5leGFtcGxlLmNvbSIsImF1ZCI6Imh0dHBzOi8vYXBpLmV4YW1wbGUuY29tIn0.signature_here

Decoded:
--------

HEADER:
{
  "alg": "RS256",         // Signing algorithm
  "typ": "JWT",           // Token type
  "kid": "key-id-123"     // Key ID (for key rotation)
}

PAYLOAD (Claims):
{
  "sub": "user_123",                       // Subject (user ID)
  "email": "alice@example.com",            // Custom claim
  "roles": ["user", "admin"],              // Custom claim
  "iat": 1711324800,                       // Issued At
  "exp": 1711328400,                       // Expiration (1 hour later)
  "iss": "https://auth.example.com",       // Issuer
  "aud": "https://api.example.com"         // Audience
}

SIGNATURE:
  RS256(
    base64urlEncode(header) + "." + base64urlEncode(payload),
    private_key
  )
```

Signing algorithms:
- **HS256** (HMAC-SHA256) -- Symmetric: the same secret key signs and verifies. Simple but requires sharing the secret between issuer and verifier.
- **RS256** (RSA-SHA256) -- Asymmetric: private key signs, public key verifies. Preferred for distributed systems because verifiers only need the public key.
- **ES256** (ECDSA-SHA256) -- Asymmetric like RS256 but with smaller keys and faster signing.

JWTs are stateless -- the server does not need to store session data. This makes them ideal for microservices where multiple services need to verify tokens independently. The downside is that revocation requires additional infrastructure (a token blacklist or short expiry times).

```python
# jwt_auth.py -- JWT authentication with FastAPI
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt  # PyJWT library

app = FastAPI()
security = HTTPBearer()

# In production, load from environment / secrets manager
PRIVATE_KEY = open("private_key.pem").read()   # For signing (RS256)
PUBLIC_KEY = open("public_key.pem").read()      # For verification
ALGORITHM = "RS256"
ISSUER = "https://auth.example.com"
AUDIENCE = "https://api.example.com"

def create_access_token(user_id: str, roles: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=7),
        "iss": ISSUER,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

def require_role(required_role: str):
    """Dependency that checks for a specific role."""
    def checker(payload: dict = Depends(verify_token)):
        if required_role not in payload.get("roles", []):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    return checker

# --- Endpoints ---

@app.post("/auth/login")
def login(username: str, password: str):
    # In practice, verify against database
    if username == "alice" and password == "secret":
        return {
            "access_token": create_access_token("user_123", ["user", "admin"]),
            "refresh_token": create_refresh_token("user_123"),
            "token_type": "bearer",
            "expires_in": 1800,
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/v1/profile")
def get_profile(payload: dict = Depends(verify_token)):
    return {"user_id": payload["sub"], "roles": payload["roles"]}

@app.get("/api/v1/admin/settings")
def admin_settings(payload: dict = Depends(require_role("admin"))):
    return {"settings": {"maintenance_mode": False}}
```

Example requests:

```bash
# Login
curl -X POST "http://localhost:8000/auth/login?username=alice&password=secret"

# Response:
# {
#   "access_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIi...",
#   "refresh_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIi...",
#   "token_type": "bearer",
#   "expires_in": 1800
# }

# Access a protected endpoint
curl http://localhost:8000/api/v1/profile \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIi..."

# Access admin endpoint without admin role
curl http://localhost:8000/api/v1/admin/settings \
  -H "Authorization: Bearer <token_without_admin_role>"

# Response: 403 {"detail": "Insufficient permissions"}
```

A full session looks something like this (the JWT strings are truncated for readability; real tokens are 300+ characters):

```console
$ curl http://localhost:8000/api/v1/profile \
    -H "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIi..."
{"user_id":"user_123","roles":["user","admin"]}

$ curl http://localhost:8000/api/v1/profile   # no Authorization header
{"detail":"Not authenticated"}

$ curl http://localhost:8000/api/v1/profile \
    -H "Authorization: Bearer expired.token.here"
{"detail":"Token has expired"}
```

**How to read this output:** the first call succeeds because `verify_token` decoded the signature with the public key and the `iss`/`aud` claims matched. The missing-header case is rejected by `HTTPBearer` before your code runs (FastAPI returns 401 automatically). The expired case is the `jwt.ExpiredSignatureError` branch -- note the verifier checks `exp` for you, so you never compare timestamps by hand. In an interview this is the crux of "stateless auth": each service validates the token independently using only the public key, with no database round-trip and no shared session store.

> **Common pitfall:** never accept `alg: none` and never let the client choose the algorithm. Always pin `algorithms=[ALGORITHM]` on `jwt.decode` as shown -- libraries that honored the token's own `alg` header allowed attackers to forge tokens by swapping RS256 for HS256 and signing with the public key as the HMAC secret.

**Refresh Tokens**

Access tokens should be short-lived (15-60 minutes) to limit the damage window if they are compromised. Refresh tokens are longer-lived (days to weeks) and are used to obtain new access tokens without requiring the user to log in again.

Token rotation is a critical security measure: each time a refresh token is used, a new refresh token is issued and the old one is invalidated. If a stolen refresh token is used after the legitimate user has already rotated it, the server can detect reuse and revoke all tokens for that user.

```python
# refresh_token_rotation.py
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
r = redis.Redis()

class RefreshRequest(BaseModel):
    refresh_token: str

@app.post("/auth/refresh")
def refresh_tokens(req: RefreshRequest):
    # Decode the refresh token
    payload = verify_refresh_token(req.refresh_token)
    user_id = payload["sub"]
    token_id = payload.get("jti")  # Unique token identifier

    # Check if this refresh token has been used before
    used_key = f"refresh_used:{token_id}"
    if r.exists(used_key):
        # Token reuse detected -- possible compromise!
        # Revoke ALL tokens for this user
        r.set(f"user_revoked:{user_id}", "1", ex=86400 * 30)
        raise HTTPException(status_code=401, detail="Token reuse detected. All sessions revoked.")

    # Mark this token as used
    r.set(used_key, "1", ex=86400 * 14)  # Keep for 14 days

    # Issue new token pair
    new_access = create_access_token(user_id, payload.get("roles", []))
    new_refresh = create_refresh_token(user_id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }
```

Store refresh tokens in HttpOnly, Secure, SameSite cookies for browser-based applications (protects against XSS). For mobile applications, use the platform's secure storage (Keychain on iOS, Keystore on Android).

**API Keys**

API keys are a simple authentication mechanism suited for server-to-server communication. They are not appropriate for user authentication because they provide no identity context and are often long-lived.

Best practices for API keys:
- **Hash before storing** -- Store only the hash in the database, like passwords. If the database is breached, the keys are useless.
- **Prefix for identification** -- Use a recognizable prefix like `sk_live_` (secret key, production) or `pk_test_` (public key, test) so keys can be visually identified and routed.
- **Rate limit per key** -- Associate rate limits with each key to prevent abuse.
- **Support rotation** -- Allow users to create new keys and revoke old ones without downtime.

```python
# api_key_auth.py
import hashlib, secrets
from fastapi import FastAPI, Security, HTTPException
from fastapi.security import APIKeyHeader

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-Key")

def generate_api_key() -> tuple[str, str]:
    """Returns (raw_key, hashed_key). Store hashed_key in DB."""
    raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key

def verify_api_key(api_key: str = Security(api_key_header)) -> dict:
    hashed = hashlib.sha256(api_key.encode()).hexdigest()
    # Look up hashed key in database
    # client = db.query("SELECT * FROM api_keys WHERE key_hash = :h", h=hashed)
    client = {"id": "client_1", "name": "Partner App"} if hashed else None
    if not client:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return client

@app.get("/api/v1/data")
def get_data(client: dict = Security(verify_api_key)):
    return {"message": f"Hello, {client['name']}"}
```

```bash
curl http://localhost:8000/api/v1/data \
  -H "X-API-Key: sk_live_abc123def456..."
```

With a valid key the request returns the client greeting; an unknown or malformed key is rejected before reaching the handler:

```console
$ curl http://localhost:8000/api/v1/data -H "X-API-Key: sk_live_abc123def456..."
{"message":"Hello, Partner App"}

$ curl http://localhost:8000/api/v1/data -H "X-API-Key: wrong_key"
{"detail":"Invalid API key"}
```

**How to read this output:** the server never compares the raw key -- it hashes the incoming value and looks up the *hash*, exactly like password verification. That is why a database breach does not leak usable keys. Note the lookup here is a plain SHA-256, which is fine for high-entropy random keys (unlike user passwords, which need a slow hash like bcrypt because they are guessable). In production you would also rate-limit per `client["id"]` so one partner cannot exhaust your capacity.

> **Common pitfall:** comparing the hash with a normal `==` can leak timing information. For secrets compared after hashing this is a minor concern, but when matching a raw token directly, use `secrets.compare_digest()` to avoid timing-attack side channels.

**Session-Based Authentication**

In session-based auth, the server creates a session record (in Redis or a database) after login and sends the session ID to the client as a cookie. On subsequent requests, the browser automatically includes the cookie, and the server looks up the session.

Advantages over JWT: easier revocation (delete the session record), no token size concerns, and no need to worry about token expiry. Disadvantages: requires server-side storage, does not scale as naturally across microservices, and requires CSRF protection because the browser sends cookies automatically.

```python
# session_auth.py
import secrets
import redis
from fastapi import FastAPI, Request, Response, HTTPException

app = FastAPI()
r = redis.Redis()

@app.post("/auth/login")
def login(request: Request, response: Response, username: str, password: str):
    # Verify credentials (simplified)
    if username != "alice" or password != "secret":
        raise HTTPException(401, "Invalid credentials")

    # Create session
    session_id = secrets.token_urlsafe(32)
    r.setex(
        f"session:{session_id}",
        3600,  # 1 hour TTL
        '{"user_id": "user_123", "roles": ["admin"]}',
    )

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,     # Not accessible via JavaScript (XSS protection)
        secure=True,       # Only sent over HTTPS
        samesite="lax",    # CSRF protection
        max_age=3600,
    )
    return {"message": "Logged in"}

@app.get("/api/v1/profile")
def profile(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(401, "Not authenticated")

    session_data = r.get(f"session:{session_id}")
    if not session_data:
        raise HTTPException(401, "Session expired")

    import json
    user = json.loads(session_data)
    return {"user_id": user["user_id"]}

@app.post("/auth/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id:
        r.delete(f"session:{session_id}")
    response.delete_cookie("session_id")
    return {"message": "Logged out"}
```

**SSO (Single Sign-On)**

SSO allows users to authenticate once and gain access to multiple applications. There are two main protocols:

- **SAML (Security Assertion Markup Language)** -- XML-based, primarily used in enterprise environments. The Identity Provider (IdP) sends a signed XML assertion to the Service Provider (SP). Mature but complex.

- **OIDC (OpenID Connect)** -- Built on top of OAuth 2.0, modern and simpler than SAML. The authorization server issues an ID token (a JWT containing user identity information) alongside the access token. OIDC is the standard for modern SSO.

The ID token contains claims like `sub` (user identifier), `email`, `name`, `email_verified`, and `at_hash` (access token hash for binding). Your application verifies the ID token signature and extracts user information without needing a separate API call.

> **Key Takeaway:** Use OAuth 2.0 Authorization Code + PKCE for user-facing applications, Client Credentials for service-to-service, and API keys for simple external integrations. Always use asymmetric signing (RS256/ES256) for JWTs in distributed systems. Short-lived access tokens + refresh token rotation is the gold standard for session management.

### Authorization

**RBAC (Role-Based Access Control)**

RBAC assigns users to roles, and roles to permissions. It is simple, widely understood, and sufficient for most applications. The user does not have direct permissions -- they inherit them through their role assignments.

```
User "Alice" --> Role "editor" --> Permissions: [read, write, publish]
User "Bob"   --> Role "viewer" --> Permissions: [read]
```

The limitation of RBAC is role explosion: as your application grows, you may end up creating dozens of narrow roles (`us-east-editor-for-department-x`). When this happens, consider ABAC.

```python
# rbac.py -- RBAC implementation
from fastapi import FastAPI, Depends, HTTPException
from enum import Enum
from functools import wraps

app = FastAPI()

class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

# Role -> permission mapping
ROLE_PERMISSIONS = {
    "viewer":  {Permission.READ},
    "editor":  {Permission.READ, Permission.WRITE},
    "admin":   {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
}

def get_current_user():
    """Simulated dependency -- in practice, decode JWT or look up session."""
    return {"id": "user_123", "roles": ["editor"]}

def require_permission(permission: Permission):
    """Dependency that checks for a specific permission."""
    def checker(user: dict = Depends(get_current_user)):
        user_permissions = set()
        for role in user.get("roles", []):
            user_permissions |= ROLE_PERMISSIONS.get(role, set())

        if permission not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission.value}' required",
            )
        return user
    return checker

@app.get("/articles")
def list_articles(user: dict = Depends(require_permission(Permission.READ))):
    return {"articles": [{"id": 1, "title": "Hello World"}]}

@app.post("/articles")
def create_article(user: dict = Depends(require_permission(Permission.WRITE))):
    return {"message": "Article created"}

@app.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    user: dict = Depends(require_permission(Permission.DELETE)),
):
    return {"message": f"Article {article_id} deleted"}
```

**ABAC (Attribute-Based Access Control)**

ABAC evaluates policies based on attributes of the user, the resource, the action, and the environment/context. It is more flexible than RBAC and can express rules like "a user can edit a document only if they belong to the same department as the document owner, and it is during business hours."

```python
# abac.py -- ABAC implementation
from dataclasses import dataclass
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException

app = FastAPI()

@dataclass
class AccessRequest:
    user_attrs: dict     # {"department": "engineering", "clearance": 3}
    resource_attrs: dict # {"department": "engineering", "classification": 2}
    action: str          # "read", "write", "delete"
    context: dict        # {"time": datetime, "ip": "10.0.0.1"}

class ABACEngine:
    def __init__(self):
        self.policies = []

    def add_policy(self, name: str, condition):
        self.policies.append({"name": name, "condition": condition})

    def is_allowed(self, request: AccessRequest) -> bool:
        for policy in self.policies:
            if policy["condition"](request):
                return True
        return False

# Initialize engine with policies
engine = ABACEngine()

# Policy: users can read resources in their own department
engine.add_policy(
    "same_department_read",
    lambda req: (
        req.action == "read"
        and req.user_attrs.get("department") == req.resource_attrs.get("department")
    ),
)

# Policy: users can only write during business hours
engine.add_policy(
    "business_hours_write",
    lambda req: (
        req.action == "write"
        and req.user_attrs.get("department") == req.resource_attrs.get("department")
        and 9 <= req.context.get("time", datetime.now()).hour < 18
    ),
)

# Policy: clearance level must meet or exceed classification
engine.add_policy(
    "clearance_check",
    lambda req: (
        req.user_attrs.get("clearance", 0) >= req.resource_attrs.get("classification", 0)
    ),
)

@app.get("/documents/{doc_id}")
def get_document(doc_id: int):
    user_attrs = {"department": "engineering", "clearance": 3}
    resource_attrs = {"department": "engineering", "classification": 2}

    access = AccessRequest(
        user_attrs=user_attrs,
        resource_attrs=resource_attrs,
        action="read",
        context={"time": datetime.now()},
    )

    if not engine.is_allowed(access):
        raise HTTPException(403, "Access denied by policy")

    return {"id": doc_id, "content": "Secret document"}
```

Tracing the request above through the engine makes the OR-semantics concrete. The user is in `engineering` with clearance 3, reading an `engineering` document classified 2:

```text
same_department_read  -> True   (action=read AND depts match)
business_hours_write  -> False  (action is "read", not "write")
clearance_check       -> True   (3 >= 2)
is_allowed()          -> True   (first matching policy wins)
```

**How to read this output:** `is_allowed` returns `True` as soon as *any* policy matches -- the loop short-circuits on the first hit, so policies here are additive grants, not a conjunction. That matters: if you instead wanted "all conditions must hold" you would have to invert the structure (default allow, deny on first failing policy). This permit-overrides design is the usual ABAC default, but mixing grant and deny rules in one list is exactly where authorization bugs hide, because rule order and combining logic become load-bearing.

> **Common pitfall:** ABAC's flexibility is also its trap -- a handful of overlapping lambdas quickly becomes impossible to reason about or audit. Once policies interact in non-obvious ways, externalize them to a real policy engine (OPA below) where they can be unit-tested and the combining algorithm is explicit.

**Policy Engines: OPA (Open Policy Agent)**

For complex authorization needs, externalize your policy decisions to a dedicated engine. OPA (Open Policy Agent) uses the Rego language to define policies, which can be tested independently, versioned, and shared across services.

```rego
# policy.rego -- OPA policy example
package authz

default allow = false

# Allow admins to do anything
allow {
    input.user.roles[_] == "admin"
}

# Allow users to read their own data
allow {
    input.action == "read"
    input.resource.owner == input.user.id
}

# Allow editors to write to their department's resources
allow {
    input.action == "write"
    input.user.roles[_] == "editor"
    input.user.department == input.resource.department
}
```

Query OPA from your Python service:

```python
# opa_client.py
import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI()
OPA_URL = "http://localhost:8181/v1/data/authz/allow"

async def check_permission(user: dict, action: str, resource: dict) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPA_URL,
            json={
                "input": {
                    "user": user,
                    "action": action,
                    "resource": resource,
                }
            },
        )
        result = response.json()
        return result.get("result", False)

@app.get("/documents/{doc_id}")
async def get_document(doc_id: int):
    user = {"id": "user_123", "roles": ["editor"], "department": "engineering"}
    resource = {"id": doc_id, "owner": "user_456", "department": "engineering"}

    allowed = await check_permission(user, "read", resource)
    if not allowed:
        raise HTTPException(403, "Access denied by OPA policy")

    return {"id": doc_id, "content": "Document content"}
```

You can probe the same policy directly against OPA's REST API to see the raw decision it returns:

```console
$ curl -s http://localhost:8181/v1/data/authz/allow \
    -d '{"input":{"user":{"id":"user_123","roles":["editor"],"department":"engineering"},"action":"read","resource":{"id":1,"owner":"user_456","department":"engineering"}}}'
{"result":false}
```

**How to read this output:** OPA evaluates every `allow` rule and returns `true` if any of them holds (Rego rules sharing a name combine as a logical OR). Walk the request: the "read your own data" rule fails because `user_456` owns the resource, not `user_123`; the "editor writes their department" rule fails because the action is `read`, not `write`; the admin rule fails because `editor != admin`. No rule matches, so the result should be the `default allow = false` -- meaning a correct policy returns `{"result":false}` and the user is denied. The lesson for production and interviews: always test the *deny* path, because `default allow = false` is the only thing standing between you and an accidental open door. A bare `{}` response (no `result` key) means the rule was undefined -- treat that as deny, which is exactly why the client code defaults to `False`.

**Row-Level Security (RLS)**

PostgreSQL's Row-Level Security feature allows you to define policies at the database level that restrict which rows a user can see or modify. This is especially powerful for multi-tenant applications, where each tenant should only see their own data.

```sql
-- Enable RLS on the orders table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own orders
CREATE POLICY user_orders ON orders
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::int);

-- Policy: users can only insert orders for themselves
CREATE POLICY user_insert_orders ON orders
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id')::int);

-- Policy: admins can see all orders
CREATE POLICY admin_all_orders ON orders
    FOR ALL
    USING (current_setting('app.current_user_role') = 'admin');
```

Set the session variable before each query:

```python
# rls_example.py -- Using RLS with SQLAlchemy
from sqlalchemy import create_engine, text, event

engine = create_engine("postgresql://user:pass@localhost/mydb")

@event.listens_for(engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    pass  # Connection-level setup if needed

def query_orders(user_id: int, role: str):
    with engine.connect() as conn:
        # Set the current user context for RLS policies
        conn.execute(text(f"SET app.current_user_id = '{user_id}'"))
        conn.execute(text(f"SET app.current_user_role = '{role}'"))

        # This query automatically filters based on RLS policies
        result = conn.execute(text("SELECT * FROM orders"))
        return result.fetchall()

# User 123 (regular user) -- only sees their own orders
user_orders = query_orders(123, "user")

# Admin -- sees all orders
all_orders = query_orders(1, "admin")
```

The same `SELECT * FROM orders` returns different rows depending on the session context, because Postgres applies the RLS policies transparently:

```text
>>> query_orders(123, "user")
[(501, 123, 'shipped'), (502, 123, 'pending')]      # only user 123's rows

>>> query_orders(1, "admin")
[(501, 123, 'shipped'), (502, 123, 'pending'),
 (503, 456, 'delivered'), (504, 789, 'cancelled')]   # every row
```

**How to read this output:** the application code never adds a `WHERE user_id = ...` clause -- the filtering lives in the database. That is the entire point of RLS: even a buggy query or a compromised ORM call cannot leak another tenant's rows, because the policy is enforced below the query. The admin sees everything because `admin_all_orders` uses `FOR ALL` with a role check. This is why RLS is the multi-tenant safety net: it turns "did every developer remember the tenant filter?" into a database invariant.

> **Common pitfall:** the `SET app.current_user_id = '{user_id}'` f-string interpolates straight into SQL. Here the value is a typed `int`, but if it ever came from user input this is an injection hole that could let a caller set themselves as admin. Use `SET LOCAL` with a bound parameter (`SET LOCAL app.current_user_id = :uid`) and scope it to the transaction so the context cannot leak across pooled connections.

**Principle of Least Privilege**

The principle of least privilege states that every user, service, and process should be granted only the minimum permissions necessary to perform its function. This is not just a best practice -- it is a fundamental security principle that limits the blast radius of any compromise.

In practice, this means:

- Default deny: start with no permissions and explicitly grant what is needed.
- Avoid wildcard permissions: `"actions": ["s3:GetObject"]` is better than `"actions": ["s3:*"]`.
- Time-bound elevated access: use temporary credentials or just-in-time access for administrative operations.
- Regular audits: periodically review who has access to what and remove stale permissions.
- Service accounts with minimal scope: each microservice should have credentials that access only the resources it needs.

> **Key Takeaway:** Start with RBAC -- it covers 80% of use cases with simple, auditable role assignments. Graduate to ABAC or a policy engine like OPA when you need fine-grained, context-aware decisions. Row-level security in PostgreSQL is a powerful safety net for multi-tenant data isolation. Always default to deny and grant the minimum access required.
