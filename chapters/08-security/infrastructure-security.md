[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 8.2 Infrastructure Security

### Secrets Management

> [!NOTE]
> **Beginner's Mental Model — Secrets Management:**
> Think of secrets management as a **secure digital bank vault with one-time, dynamic access cards**. Instead of printing your house keys (API keys, database passwords) on postcards and sharing them with everyone (hardcoding them in your code or committing them to Git), you place the physical keys inside the vault. When an employee (an application service) needs to get inside, they must authenticate at the vault door, which issues them a temporary, single-use keycard that automatically expires after its task is complete. This keeps the keys safe, tracks who used them and when, and makes it easy to replace a key without changing the locks on every door.

Secrets -- API keys, database credentials, encryption keys, certificates -- are the crown jewels of your infrastructure. A single leaked secret can lead to a full system compromise. Proper secrets management means storing secrets securely, rotating them regularly, auditing access, and ensuring they never appear in source code or logs.

#### HashiCorp Vault

HashiCorp Vault is a dedicated secrets management tool that provides dynamic secrets (generated on demand with short TTLs), encryption as a service, PKI certificate management, and fine-grained access control with audit logging.

**Setting up and using Vault with a Python application:**

```bash
# Install and start Vault (development mode for learning -- never use dev mode in production)
vault server -dev

# In another terminal:
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='your-root-token'

# Store a secret
vault kv put secret/myapp/database \
    username="db_user" \
    password="s3cur3P@ssw0rd" \
    host="db.internal.example.com" \
    port="5432"

# Read a secret
vault kv get secret/myapp/database

# Create a policy for your application (least privilege)
vault policy write myapp-policy - <<EOF
path "secret/data/myapp/*" {
  capabilities = ["read"]
}
path "database/creds/myapp-role" {
  capabilities = ["read"]
}
EOF

# Create an AppRole for machine authentication
vault auth enable approle
vault write auth/approle/role/myapp \
    token_policies="myapp-policy" \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_ttl=720h
```

Running `vault kv get secret/myapp/database` prints something like:

```text
====== Secret Path ======
secret/data/myapp/database

======= Metadata =======
Key                Value
---                -----
created_time       2026-06-04T10:12:03.482Z
custom_metadata    <nil>
deletion_time      n/a
destroyed          false
version            1

====== Data ======
Key         Value
---         -----
host        db.internal.example.com
password    s3cur3P@ssw0rd
port        5432
username    db_user
```

**How to read this output:** the KV v2 engine wraps every secret in versioned metadata, which is why the path you read is `secret/data/myapp/...` even though you wrote to `secret/myapp/...` -- the `data/` segment is injected automatically and trips up most newcomers. The `version` field means you can roll back to a prior value, and `destroyed: false` means a soft-deleted secret is still recoverable until explicitly destroyed. In an interview, the giveaway that someone has actually run Vault is that they know the policy path must be `secret/data/myapp/*` (with `data/`) even though the CLI write path omits it.

**Python application using Vault (with hvac library):**

```python
# pip install hvac

import hvac
import os

class VaultClient:
    def __init__(self):
        self.client = hvac.Client(
            url=os.environ.get('VAULT_ADDR', 'https://vault.internal.example.com:8200'),
        )
        # Authenticate using AppRole (preferred for applications)
        role_id = os.environ.get('VAULT_ROLE_ID')
        secret_id = os.environ.get('VAULT_SECRET_ID')
        self.client.auth.approle.login(
            role_id=role_id,
            secret_id=secret_id,
        )

    def get_secret(self, path: str) -> dict:
        """Read a secret from Vault's KV v2 engine."""
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response['data']['data']

    def get_database_credentials(self) -> dict:
        """Get dynamic database credentials (auto-expire, auto-rotate)."""
        response = self.client.secrets.databases.generate_credentials(name='myapp-role')
        return {
            'username': response['data']['username'],
            'password': response['data']['password'],
            'ttl': response['lease_duration'],  # Credentials expire after this many seconds
        }


# Usage in Django settings.py:
vault = VaultClient()

# Static secrets
app_secrets = vault.get_secret('myapp/config')
SECRET_KEY = app_secrets['django_secret_key']
EMAIL_HOST_PASSWORD = app_secrets['email_password']

# Dynamic database credentials (auto-rotated by Vault)
db_creds = vault.get_database_credentials()
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'myapp',
        'USER': db_creds['username'],      # Unique, short-lived username
        'PASSWORD': db_creds['password'],  # Auto-expires
        'HOST': 'db.internal.example.com',
        'PORT': '5432',
    }
}
```

**Vault encryption as a service (Transit engine):**

```python
# Encrypt sensitive data without managing encryption keys yourself

# Enable the transit engine (one-time setup):
# vault secrets enable transit
# vault write -f transit/keys/myapp-encryption

class VaultEncryption:
    def __init__(self, vault_client: hvac.Client, key_name: str = 'myapp-encryption'):
        self.client = vault_client
        self.key_name = key_name

    def encrypt(self, plaintext: str) -> str:
        """Encrypt data using Vault's transit engine."""
        import base64
        encoded = base64.b64encode(plaintext.encode()).decode()
        result = self.client.secrets.transit.encrypt_data(
            name=self.key_name,
            plaintext=encoded,
        )
        return result['data']['ciphertext']  # e.g., "vault:v1:abc123..."

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt data using Vault's transit engine."""
        import base64
        result = self.client.secrets.transit.decrypt_data(
            name=self.key_name,
            ciphertext=ciphertext,
        )
        return base64.b64decode(result['data']['plaintext']).decode()

# Usage:
enc = VaultEncryption(vault.client)
encrypted_ssn = enc.encrypt("123-45-6789")
# Store encrypted_ssn in your database
# Vault manages key rotation -- you just call encrypt/decrypt.

decrypted_ssn = enc.decrypt(encrypted_ssn)
# "123-45-6789"
```

#### AWS Secrets Manager / Parameter Store

For AWS-hosted applications, AWS Secrets Manager and Systems Manager Parameter Store provide managed secret storage with IAM-based access control and optional automatic rotation.

```python
# pip install boto3

import boto3
import json

# AWS Secrets Manager
def get_secret(secret_name: str, region: str = "us-east-1") -> dict:
    """Retrieve a secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage in Django settings.py:
db_secret = get_secret("prod/myapp/database")
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_secret['dbname'],
        'USER': db_secret['username'],
        'PASSWORD': db_secret['password'],
        'HOST': db_secret['host'],
        'PORT': db_secret['port'],
    }
}


# AWS Systems Manager Parameter Store (simpler, lower cost)
def get_parameter(name: str, region: str = "us-east-1") -> str:
    """Retrieve a parameter from AWS SSM Parameter Store."""
    client = boto3.client('ssm', region_name=region)
    response = client.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

SECRET_KEY = get_parameter("/prod/myapp/django-secret-key")
```

#### GCP Secret Manager

On Google Cloud, Secret Manager is the managed equivalent, with versioned secrets and IAM-based access control. Access is granted to a service account rather than to a distributed key.

```python
# pip install google-cloud-secret-manager
from google.cloud import secretmanager

def get_gcp_secret(project_id: str, secret_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Usage in settings.py:
SECRET_KEY = get_gcp_secret("my-project", "django-secret-key")
```

The client authenticates via **Application Default Credentials** -- on GKE or Cloud Run it picks up the workload's bound service account automatically, so no static key file ever lands on disk.

#### Kubernetes: external-secrets and Workload Identity

A raw Kubernetes `Secret` is only base64-encoded (not encrypted) in etcd, and committing it to git defeats the purpose. The **External Secrets Operator (ESO)** solves this: secrets live in a real backend (Vault, AWS/GCP Secret Manager) and ESO syncs them into native `Secret` objects at runtime, so the cluster manifest contains only a *reference*, never the value.

```yaml
# The ExternalSecret references a value in the cloud provider; no secret is in git.
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: myapp-db
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager   # points at the SecretStore/backend config
    kind: SecretStore
  target:
    name: myapp-db-secret       # the native K8s Secret ESO will create/sync
  data:
    - secretKey: DATABASE_PASSWORD
      remoteRef:
        key: prod/myapp/database
        property: password
```

#### Workload Identity / Cloud IAM Roles vs Static Keys

The most important secrets-management principle for cloud workloads is to **eliminate long-lived static keys entirely**. Instead of baking an access key into the app, bind the workload's identity to a cloud IAM role and let the platform mint short-lived credentials automatically:

- **AWS**: IAM Roles for Service Accounts (IRSA) on EKS, or instance/task roles on EC2/ECS. The SDK obtains temporary credentials (with a TTL) from the metadata service or via OIDC -- no static `AWS_SECRET_ACCESS_KEY`.
- **GCP**: Workload Identity binds a Kubernetes service account to a GCP service account; ADC issues short-lived tokens.
- **Azure**: Managed Identities / Workload Identity provide the same.

These credentials are **dynamic and short-lived**: they expire in minutes to hours and rotate transparently, so a leaked token has a tiny exploitation window and there is no static key to steal in the first place. The same logic underpins Vault's dynamic database credentials shown above -- a unique, auto-expiring username/password per workload beats one shared, permanent DB password. Prefer this model over static keys everywhere it is available.

#### Environment Variables and .env Files

The Twelve-Factor App methodology recommends storing configuration in environment variables. For local development, `.env` files provide a convenient way to manage these variables without committing secrets to version control.

**Project setup for secrets management with .env files:**

```
project/
    .env                # Local development secrets (NEVER commit)
    .env.example        # Template with placeholder values (committed to git)
    .gitignore          # Must include .env
    settings.py
```

**.gitignore -- prevent accidental secret commits:**

```gitignore
# Secrets and environment files
.env
.env.local
.env.production
*.pem
*.key
*.p12

# Never commit these
secrets/
credentials/
```

**.env.example -- committed to git as a template:**

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/myapp

# Django
DJANGO_SECRET_KEY=change-me-to-a-random-50-character-string
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# External services
STRIPE_API_KEY=sk_test_...
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.example.com
EMAIL_HOST_USER=noreply@example.com
EMAIL_HOST_PASSWORD=your-email-password
```

**.env -- actual secrets for local development (NEVER committed):**

```bash
DATABASE_URL=postgresql://dev_user:dev_password@localhost:5432/myapp_dev
DJANGO_SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
STRIPE_API_KEY=your_stripe_test_key_here
```

**Loading .env in Django settings:**

```python
# pip install python-dotenv

# settings.py
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file (only needed for local development;
# in production, use real environment variables or a secrets manager)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Read configuration from environment variables
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable is required")

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')

# Database (using dj-database-url for URL-based config)
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
    )
}

# External services
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
```

**Production environments -- use real environment variables, not .env files:**

```bash
# Docker Compose -- secrets via environment variables
# docker-compose.yml
services:
  web:
    build: .
    environment:
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
    env_file:
      - .env.production  # Only for non-sensitive config; prefer secrets for sensitive values

# Docker with secrets (Swarm mode):
# docker-compose.yml
services:
  web:
    build: .
    secrets:
      - db_password
      - django_secret_key
secrets:
  db_password:
    external: true
  django_secret_key:
    external: true

# Kubernetes -- use Secrets objects
# kubectl create secret generic myapp-secrets \
#   --from-literal=DJANGO_SECRET_KEY='your-key' \
#   --from-literal=DATABASE_PASSWORD='your-password'
```

#### Secret Detection in CI/CD

Preventing secrets from being committed to version control is critical. Once a secret is in a git repository, it remains in the history even after deletion. Automated secret detection tools can catch mistakes before they become breaches.

```bash
# Install detect-secrets (Yelp)
pip install detect-secrets

# Generate a baseline of known secrets (false positives to ignore)
detect-secrets scan > .secrets.baseline

# Add as a pre-commit hook
# .pre-commit-config.yaml
# repos:
#   - repo: https://github.com/Yelp/detect-secrets
#     rev: v1.4.0
#     hooks:
#       - id: detect-secrets
#         args: ['--baseline', '.secrets.baseline']

# Scan git history for leaked secrets
pip install trufflehog
trufflehog git file://. --only-verified

# Alternative: gitleaks
# gitleaks detect --source . --verbose
```

When TruffleHog finds a live credential it has confirmed against the provider's API, the output looks like:

```text
🐷🔑🐷  TruffleHog. Unearth your secrets. 🐷🔑🐷

Found verified result 🐷🔑
Detector Type: AWS
Decoder Type: PLAIN
Raw result: AKIAIOSFODNN7EXAMPLE
Commit: 4f1c2e9a8b7d6c5e4f3a2b1c0d9e8f7a6b5c4d3e
File: config/settings_old.py
Line: 42
Repository: file://.
Timestamp: 2026-06-04 10:31:55 +0000
```

**What's happening:** `--only-verified` is the flag that separates noise from emergencies -- TruffleHog actually calls AWS (or GitHub, Stripe, etc.) with the candidate key, and only reports it if the provider confirms it is live. A "verified" hit means the secret is real, valid, and exploitable right now, so it warrants immediate rotation, not just deletion. The `Commit` and `Line` fields matter because deleting the file does nothing: the credential lives forever in git history, so the only safe remediation is to rotate the secret at the source and treat it as compromised.

> **Common pitfall:** Removing a leaked secret with a follow-up commit feels like a fix but is not -- anyone with the repo can `git checkout` the old commit and read it. Always rotate the credential, and only then optionally rewrite history with `git filter-repo` or BFG.

#### Encryption

All data should be encrypted both at rest and in transit. Application-level encryption provides an additional layer of protection for particularly sensitive fields.

```python
# Encryption at the application level using the cryptography library
# pip install cryptography

from cryptography.fernet import Fernet
import os

# Generate and store the key securely (e.g., in Vault or environment variable)
# key = Fernet.generate_key()  # Run once, store the result securely
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY').encode()
fernet = Fernet(ENCRYPTION_KEY)

class EncryptedField:
    """Encrypt sensitive fields before storing in the database."""

    @staticmethod
    def encrypt(value: str) -> str:
        return fernet.encrypt(value.encode()).decode()

    @staticmethod
    def decrypt(encrypted_value: str) -> str:
        return fernet.decrypt(encrypted_value.encode()).decode()

# Usage:
ssn_encrypted = EncryptedField.encrypt("123-45-6789")
# Store ssn_encrypted in the database

ssn_decrypted = EncryptedField.decrypt(ssn_encrypted)
# "123-45-6789"


# Django model with encrypted fields (using django-encrypted-model-fields):
# pip install django-encrypted-model-fields
from encrypted_model_fields.fields import EncryptedCharField

class Patient(models.Model):
    name = models.CharField(max_length=100)
    ssn = EncryptedCharField(max_length=11)          # Encrypted at rest
    medical_notes = EncryptedTextField()              # Encrypted at rest
    email = models.EmailField()                       # Not encrypted (used for lookups)
```

TLS configuration ensures all data in transit is encrypted:

```nginx
# Nginx TLS configuration (modern profile)
server {
    listen 443 ssl http2;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # OCSP stapling for faster TLS handshakes
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # Session tickets and caching
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;  # Disabled for forward secrecy
}
```

> **Key Takeaway:** Never store secrets in source code. Use a secrets manager (Vault, AWS Secrets Manager) in production and .env files only for local development. Encrypt sensitive data at rest and in transit. Run secret detection tools as pre-commit hooks to catch accidental leaks before they are pushed.

---

### Compliance & Best Practices

#### GDPR (General Data Protection Regulation)

GDPR is the European Union's data protection regulation that applies to any organization processing data of EU residents, regardless of where the organization is based. Non-compliance can result in fines up to 4% of annual global revenue or 20 million euros, whichever is greater.

Key technical requirements and their implementations:

```python
# Data minimization: only collect what you need
class UserRegistrationForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    # DO NOT collect: date of birth, gender, phone number
    # unless there is a specific, documented business need.

# Right to erasure (right to be forgotten)
def delete_user_data(user_id: int):
    """Permanently delete all user data. Required by GDPR Article 17."""
    user = User.objects.get(id=user_id)

    # Delete related data
    Comment.objects.filter(user=user).delete()
    Order.objects.filter(user=user).update(
        # Anonymize rather than delete if needed for financial records
        user=None,
        customer_name="[DELETED]",
        customer_email="[DELETED]",
    )
    UserProfile.objects.filter(user=user).delete()
    AuditLog.objects.filter(user=user).update(
        user=None,
        ip_address="0.0.0.0",
    )

    # Finally delete the user
    user.delete()

    # Log the deletion (without PII)
    logger.info(f"User data deleted for user_id={user_id} per GDPR erasure request")


# Data portability (export user data as JSON)
def export_user_data(user_id: int) -> dict:
    """Export all user data in a machine-readable format. GDPR Article 20."""
    user = User.objects.get(id=user_id)
    return {
        "personal_info": {
            "email": user.email,
            "name": user.get_full_name(),
            "date_joined": user.date_joined.isoformat(),
        },
        "orders": list(
            Order.objects.filter(user=user).values(
                'id', 'created_at', 'total', 'status'
            )
        ),
        "comments": list(
            Comment.objects.filter(user=user).values(
                'id', 'text', 'created_at'
            )
        ),
    }


# Consent management
class ConsentRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=100)  # e.g., "marketing_email", "analytics"
    granted = models.BooleanField()
    timestamp = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField()
    consent_text_version = models.CharField(max_length=20)  # Track which text they agreed to

    class Meta:
        # Keep a full history of consent changes
        ordering = ['-timestamp']


# Data retention: automatically delete old data
from django.utils import timezone
from datetime import timedelta

def enforce_data_retention():
    """Run as a periodic task (e.g., daily cron job)."""
    cutoff = timezone.now() - timedelta(days=365 * 3)  # 3-year retention

    # Delete old audit logs
    AuditLog.objects.filter(created_at__lt=cutoff).delete()

    # Anonymize old order data
    Order.objects.filter(
        created_at__lt=cutoff,
        customer_email__isnull=False,
    ).update(
        customer_email="[EXPIRED]",
        customer_name="[EXPIRED]",
        shipping_address="[EXPIRED]",
    )

    # Delete inactive accounts
    inactive_cutoff = timezone.now() - timedelta(days=365 * 2)
    User.objects.filter(
        last_login__lt=inactive_cutoff,
        is_active=True,
    ).update(is_active=False)
    # Notify users before deletion; schedule actual deletion after grace period


# Breach notification logging
class DataBreachLog(models.Model):
    detected_at = models.DateTimeField(auto_now_add=True)
    reported_to_authority_at = models.DateTimeField(null=True)  # Must be within 72 hours
    description = models.TextField()
    affected_records = models.IntegerField()
    remediation_steps = models.TextField()
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
```

#### CCPA (California Consumer Privacy Act)

CCPA (as amended by the CPRA) is the U.S. analogue to GDPR for California residents. The technical obligations overlap heavily with GDPR -- right to know what data you hold, right to delete, right to data portability -- so a system built for GDPR erasure and export (above) largely satisfies CCPA. The notable differences:

- **Right to opt out of "sale"/sharing**: you must honor a "Do Not Sell or Share My Personal Information" signal, including the browser-level **Global Privacy Control (GPC)** header.
- **No prior consent required to collect** (unlike GDPR's lawful-basis-first model); the emphasis is on disclosure and opt-out rather than opt-in.

```python
# Honor the Global Privacy Control signal (Sec-GPC: 1)
def respects_gpc(request) -> bool:
    return request.headers.get("Sec-GPC") == "1"

def track_for_ads(request, user):
    if respects_gpc(request) or not user.consent.get("ad_personalization"):
        return  # do not share/sell behavioral data
    enqueue_ad_event(user)
```

#### PCI-DSS (Payment Card Data)

If you touch cardholder data, PCI-DSS applies. The single most important architectural decision is **scope reduction**: the less card data flows through your systems, the smaller (and cheaper) your compliance burden.

- **Never store raw PANs (card numbers) or CVVs.** Storing the CVV after authorization is forbidden outright.
- **Tokenize**: let a payment provider (Stripe, Braintree, Adyen) capture the card directly via their hosted fields/SDK and hand you back an opaque token. Your servers store only the token and charge against it -- the real card number never enters your network, dropping you to the simplest SAQ scope.

```python
# The browser sends the card straight to Stripe; your server only sees a token.
import stripe

def charge(request):
    token = request.POST["stripe_token"]   # opaque, e.g. "tok_visa" -> "pm_..."
    stripe.PaymentIntent.create(
        amount=5000, currency="usd",
        payment_method=token, confirm=True,
    )
    # Store only: provider token, last4, brand, expiry. Never the full PAN or CVV.
    Payment.objects.create(user=request.user, provider_token=token, last4="4242")
```

#### SOC 2, ISO 27001, and SBOM

- **SOC 2 / ISO 27001** are control *frameworks*, not laws. You demonstrate that you operate a set of controls -- access control, change management, monitoring, incident response, vendor management -- and an independent auditor attests to it (SOC 2 Type II audits the controls *over a period*, typically 6-12 months). For engineering, this mostly means: enforce least-privilege access, log and review changes, run the monitoring/alerting and incident processes you claim to, and keep the evidence (access reviews, ticket history, on-call records).
- **SBOM (Software Bill of Materials)**: a machine-readable inventory of every component and dependency in your software (formats: CycloneDX, SPDX). When a new CVE drops (think Log4Shell), an SBOM lets you answer "are we affected, and where?" in minutes instead of days, and it is increasingly required by customers and regulators.

```bash
# Generate a CycloneDX SBOM for a Python project
pip install cyclonedx-bom
cyclonedx-py environment -o sbom.json

# Then scan the SBOM against vulnerability databases (e.g., grype, trivy)
grype sbom:./sbom.json
```

#### Data Residency and Privacy by Design

- **Data residency / sovereignty**: some jurisdictions require that personal data be stored (and sometimes processed) within specific geographic boundaries. Architect for it by pinning storage to in-region buckets/databases, partitioning data by region, and ensuring backups and logs do not silently cross borders.
- **Privacy by design**: bake privacy into the architecture rather than bolting it on. In practice this means data minimization (don't collect what you don't need), purpose limitation (use data only for the stated reason), encryption at rest and in transit by default, short retention windows, and pseudonymization/anonymization wherever the raw identity isn't required.

#### Dependency Scanning

Third-party dependencies are a major attack vector. A single vulnerable library can compromise your entire application. Automated scanning and updating is essential.

{% raw %}

```bash
# Python: Safety (checks for known vulnerabilities in installed packages)
pip install safety
safety check --full-report

# Python: pip-audit (maintained by the Python Packaging Authority)
pip install pip-audit
pip-audit

# Pin exact versions in requirements.txt for reproducible builds:
# requirements.txt
Django==5.1.3
psycopg2-binary==2.9.9
requests==2.31.0

# Use Dependabot (GitHub) or Renovate for automated dependency updates:
# .github/dependabot.yml
# version: 2
# updates:
#   - package-ecosystem: "pip"
#     directory: "/"
#     schedule:
#       interval: "weekly"
#     open-pull-requests-limit: 10
#     reviewers:
#       - "security-team"

# Snyk integration (CI/CD pipeline):
# In your CI config (e.g., GitHub Actions):
# - name: Run Snyk to check for vulnerabilities
#   uses: snyk/actions/python@master
#   with:
#     command: test
#   env:
#     SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

{% endraw %}

A `pip-audit` run against an environment with a known-vulnerable package prints something like:

```text
Found 2 known vulnerabilities in 1 package
Name      Version  ID                  Fix Versions
--------  -------  ------------------  ------------
requests  2.31.0   GHSA-9wx4-h78v-vm56 2.32.0
requests  2.31.0   PYSEC-2024-47       2.32.0
```

**How to read this output:** each row is one CVE/advisory affecting an installed package, and the `Fix Versions` column tells you the minimum safe upgrade -- this is exactly the report that drives a Dependabot or Renovate pull request. The process exits non-zero when vulnerabilities are found, which is what makes it usable as a CI gate: a failing exit code blocks the merge until the dependency is bumped. In production terms, a clean `pip-audit` does not prove you are safe (the advisory database lags real disclosures), but a dirty one is an unambiguous signal you are shipping a known hole.

> **Common pitfall:** Pinning exact versions in `requirements.txt` makes builds reproducible but also freezes you on vulnerable releases until something forces an upgrade. Pinning is correct -- but it only works paired with automated scanning that nudges those pins forward.

#### Penetration Testing and Static/Dynamic Analysis

Regular security testing is non-negotiable for production systems. A combination of automated tools and manual penetration testing provides the most comprehensive coverage.

```bash
# Static Application Security Testing (SAST)
# Bandit: finds common security issues in Python code
pip install bandit
bandit -r ./myapp/ -f json -o bandit-report.json

# Common issues Bandit finds:
# - Use of eval(), exec()
# - Hardcoded passwords
# - Use of assert for security checks (assert is removed with -O flag)
# - Weak cryptographic algorithms
# - SQL injection via string formatting
# - Use of pickle with untrusted data

# Semgrep: pattern-based static analysis with custom rules
pip install semgrep
semgrep --config auto ./myapp/

# A single Bandit finding (from the JSON report or terminal) reads like:
# >> Issue: [B602:subprocess_popen_with_shell_equals_true] subprocess
#    call with shell=True identified, security issue.
#    Severity: High   Confidence: High
#    Location: ./myapp/tasks.py:88
#    87  cmd = f"ping {user_host}"
#    88  subprocess.Popen(cmd, shell=True)

# Dynamic Application Security Testing (DAST)
# OWASP ZAP: automated scanner for running applications
# docker run -t ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
#     -t https://staging.example.com -r zap-report.html

# Integrate into CI/CD:
# .github/workflows/security.yml
# jobs:
#   security:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v4
#       - name: SAST - Bandit
#         run: |
#           pip install bandit
#           bandit -r ./myapp/ -ll  # Only medium and high severity
#       - name: SAST - Semgrep
#         uses: semgrep/semgrep-action@v1
#       - name: Dependency Audit
#         run: |
#           pip install pip-audit
#           pip-audit
```

**How to read a SAST finding:** each issue carries a rule ID (`B602`), a *severity* (how bad it is if exploited) and a *confidence* (how sure the tool is it is a real match), plus the exact file and line. The severity/confidence split is the key insight -- in CI you typically gate on high-severity, high-confidence findings (`bandit -r ./myapp/ -ll` filters to medium-and-up) so the build fails on genuine `shell=True` command injection while a noisy low-confidence guess does not block every merge. SAST proves a pattern *exists* in source; DAST tools like OWASP ZAP prove a vulnerability is *reachable* on the running app -- you want both because a dangerous-looking line behind dead code is lower priority than the same line on a live request path.

#### Zero-Trust Architecture

Zero-trust is a security model based on the principle "never trust, always verify." Unlike traditional perimeter-based security where everything inside the network is trusted, zero-trust treats every request as potentially hostile, regardless of its origin.

Core principles and implementation patterns:

```python
# 1. Identity-based access: Every request must carry verified identity
# Use JWT tokens with short expiry and refresh token rotation

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.settings import api_settings

# settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),    # Short-lived access tokens
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,                     # New refresh token on each refresh
    'BLACKLIST_AFTER_ROTATION': True,                   # Invalidate old refresh tokens
    'SIGNING_KEY': os.environ.get('JWT_SIGNING_KEY'),
    'ALGORITHM': 'HS256',
}


# 2. Continuous authentication: Re-verify for sensitive operations
from django.contrib.auth import authenticate

def sensitive_operation(request):
    """Require re-authentication for sensitive actions."""
    password = request.POST.get('current_password')
    user = authenticate(username=request.user.username, password=password)
    if user is None:
        return JsonResponse({"error": "Please re-enter your password"}, status=403)
    # Proceed with sensitive operation
    ...


# 3. Principle of least privilege: Grant minimum necessary permissions
# Django REST Framework with fine-grained permission classes
from rest_framework.permissions import BasePermission

class IsOwnerOrReadOnly(BasePermission):
    """Object-level permission: only the owner can modify."""
    def has_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return obj.owner == request.user

class HasSpecificScope(BasePermission):
    """Check that the token has the required scope."""
    def __init__(self, required_scope):
        self.required_scope = required_scope

    def has_permission(self, request, view):
        token_scopes = getattr(request.auth, 'scopes', [])
        return self.required_scope in token_scopes


# 4. Microsegmentation: Internal services also authenticate
# Service-to-service authentication using mutual TLS (mTLS) or service tokens
import requests

def call_internal_service(endpoint: str, data: dict) -> dict:
    """Authenticate when calling internal microservices."""
    service_token = get_service_token()  # From Vault or environment
    response = requests.post(
        f"https://payment-service.internal/{endpoint}",
        json=data,
        headers={"Authorization": f"Bearer {service_token}"},
        verify="/etc/ssl/certs/internal-ca.pem",  # Verify internal CA
        cert=("/etc/ssl/certs/myapp.pem", "/etc/ssl/private/myapp-key.pem"),  # mTLS
        timeout=5,
    )
    response.raise_for_status()
    return response.json()
```

Network-level zero-trust with Kubernetes network policies:

```yaml
# Kubernetes NetworkPolicy: deny all traffic by default,
# then explicitly allow only what is needed.

# Default deny all ingress traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress

---
# Allow the web app to receive traffic only from the ingress controller
# and to connect only to the database and Redis
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-app-policy
spec:
  podSelector:
    matchLabels:
      app: web
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: ingress-nginx
      ports:
        - port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - port: 6379
    - to:  # Allow DNS resolution
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
```

> **Key Takeaway:** Security is not a feature you add at the end -- it is a discipline applied at every layer, from code to infrastructure. Use defense in depth: parameterized queries, output encoding, security headers, secrets management, encrypted communications, dependency scanning, automated security testing, and zero-trust architecture. The cost of building security in from the start is always lower than the cost of a breach.

*Last reviewed: 2026-06-08*
