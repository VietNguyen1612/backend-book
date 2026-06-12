[Back to Chapter](README.md) | [Back to Book](../../README.md)

# 5.4 WebAuthn & Passkeys

Section 5.3 covered passwords, OAuth, and JWTs -- all of which ultimately rest on a *shared secret* (a password, a client secret, a signing key) that can be phished, leaked, or replayed. In production those failure modes are not hypothetical: breached password dumps feed credential-stuffing attacks against every service where users reused a password, and a convincing phishing page can capture not just the password but the one-time code typed after it. WebAuthn removes the shared secret from the login path entirely by using public-key cryptography, and **passkeys** are the user-friendly packaging that has made it mainstream. For a backend engineer this is no longer a niche topic -- the major platforms ship passkey support by default, and "add passkey login" is now an ordinary product request that lands on the server team.

By the end of this section you should be able to answer: what actually changes hands during a WebAuthn login, and why does a breach of the credential database yield nothing an attacker can use? Why is the protocol phishing-resistant by construction rather than by user vigilance? What makes a credential a *passkey* rather than just a WebAuthn credential, and what does account recovery look like when there is no password to reset?

We begin with why passwordless authentication is worth the migration cost, then build the four-party trust model that everything else hangs on. With the model in place, we walk the two ceremonies end to end -- registration (attestation), which creates a credential, and authentication (assertion), which proves possession of it -- with working server and client code. We then look at passkeys themselves, contrasting synced and device-bound credentials, and close with the security properties and operational gotchas that decide whether a deployment holds up in production.

## Why Passwordless

Passwords fail in predictable ways: users reuse them, attackers phish them, and a single server breach leaks a reusable credential. Even with a password *plus* TOTP/SMS, the second factor is still a shared secret a convincing phishing page can capture and relay in real time (adversary-in-the-middle).

WebAuthn (a W3C standard; **FIDO2** = WebAuthn + the CTAP protocol that talks to roaming authenticators) replaces the shared secret with an **asymmetric key pair generated per site**:

- The **private key never leaves the authenticator** (the device's secure element, TPM, or a hardware security key). The server never sees it and cannot leak it.
- The server stores only the **public key**. A breach of that database yields nothing an attacker can log in with.
- Each assertion is **bound to the site's origin**, so a phishing page on `evil.com` cannot produce a valid signature for `example.com` -- WebAuthn is *phishing-resistant by construction*, not by user vigilance.

## The WebAuthn Model

Four parties cooperate. Knowing which one does what is the whole mental model:

```
  WebAuthn trust model
  ====================

  +----------------+        +------------------+        +-------------------+
  |  Authenticator |  CTAP  |  Client (browser)|  HTTPS |  Relying Party    |
  | (TPM / Secure  |<------>| navigator.       |<------>|  - JS frontend    |
  |  Enclave / key)|        | credentials.*    |        |  - RP server (you)|
  +----------------+        +------------------+        +-------------------+
   holds PRIVATE key         enforces ORIGIN +           holds PUBLIC key +
   signs challenges          RP ID, mediates UX          challenge, verifies

  RP ID  = the registrable domain (e.g. "example.com"); the credential is
           scoped to it and to its subdomains. The browser refuses to use a
           credential whose RP ID does not match the page's origin.
```

The **relying party (RP)** is your application. The **authenticator** generates and guards the key pair. The **client** (the browser's `navigator.credentials` API) sits in the middle and enforces that the authenticator only ever signs for the origin the user is actually on -- this origin check is what defeats phishing.

There are two ceremonies: **registration** (attestation) creates a credential; **authentication** (assertion) proves possession of it. Both follow the same shape: the server issues a random **challenge**, the authenticator signs over it, and the server verifies. The challenge makes every ceremony single-use and replay-proof.

## Registration (Attestation) Ceremony

With the trust model in place, we can follow the first ceremony end to end. Registration is where the key pair is born: the authenticator generates it, the user approves with a biometric or PIN, and the server records the public half against the account.

```
  Registration
  ============

  Browser                         RP server                  Authenticator
    |  POST /register/begin           |                            |
    |-------------------------------->|  create challenge,         |
    |                                 |  PublicKeyCredential-      |
    |   options (challenge, rp,       |  CreationOptions; store    |
    |<--------------------------------|  challenge in session      |
    | navigator.credentials.create()  |                            |
    |--------------------------------------------------------------->| generate
    |                                 |                            |  keypair,
    |   attestation (credential id,   |                            |  user verifies
    |   public key, signature)        |                            |  (biometric/PIN)
    |<---------------------------------------------------------------|
    |  POST /register/complete        |                            |
    |-------------------------------->|  verify challenge, origin, |
    |                                 |  RP ID hash; store public  |
    |   { verified: true }            |  key + credential id +     |
    |<--------------------------------|  sign_count for this user  |
```

On the **server**, use a maintained library (e.g. [`py_webauthn`](https://github.com/duo-labs/py_webauthn)) rather than hand-rolling COSE/CBOR parsing and attestation verification -- this is exactly the kind of crypto plumbing you should not reimplement:

```python
# server: begin registration
from webauthn import generate_registration_options, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement,
)

def register_begin(user):
    options = generate_registration_options(
        rp_id="example.com",
        rp_name="Example App",
        user_id=user.id.bytes,            # opaque, stable, NOT the email/username
        user_name=user.email,
        user_display_name=user.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            # resident_key=required -> a *discoverable* credential, i.e. a passkey
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    cache.set(f"reg_chal:{user.id}", options.challenge, timeout=300)  # bytes, single-use
    return options_to_json(options)       # send to the browser as-is
```

```python
# server: complete registration
from webauthn import verify_registration_response

def register_complete(user, body):       # body = the browser's attestation JSON
    verification = verify_registration_response(
        credential=body,
        expected_challenge=cache.get(f"reg_chal:{user.id}"),
        expected_rp_id="example.com",
        expected_origin="https://example.com",   # exact origin, scheme included
    )
    Credential.objects.create(
        user=user,
        credential_id=verification.credential_id,            # bytes -> store
        public_key=verification.credential_public_key,       # bytes -> store
        sign_count=verification.sign_count,
        transports=body.get("response", {}).get("transports", []),
    )
    cache.delete(f"reg_chal:{user.id}")
```

On the **client**, `@simplewebauthn/browser` handles the base64url/`ArrayBuffer` encoding that `navigator.credentials.create()` requires (a common source of hand-rolled bugs):

```javascript
import { startRegistration } from "@simplewebauthn/browser";

const options = await fetch("/register/begin", { method: "POST" }).then((r) => r.json());
const attestation = await startRegistration(options);   // prompts biometric/PIN
const result = await fetch("/register/complete", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(attestation),
}).then((r) => r.json());
// result.verified === true
```

**How to read this flow:** the security-critical line is the server's `verify_registration_response`. It recomputes the SHA-256 hash of your RP ID and checks it against the authenticator data, confirms the `expected_origin` matches exactly (so a credential minted on `https://example.com` cannot be created from `https://example.com.evil.com`), and confirms the challenge is the one *you* issued (defeating replay). `user_id` must be an opaque, stable handle -- never the email, because it is stored on the authenticator and used to look the account up during usernameless login. Setting `resident_key=REQUIRED` is what turns an ordinary credential into a **passkey** (a *discoverable* credential the authenticator can surface without the server first telling it which credential to use).

## Authentication (Assertion) Ceremony

Authentication mirrors registration, but now the authenticator *signs* the challenge with the private key it already holds, and the server verifies that signature with the stored public key.

```python
# server: begin authentication
from webauthn import generate_authentication_options, options_to_json

def login_begin(user=None):
    # For usernameless/passkey login, omit allow_credentials entirely and let
    # the authenticator offer its discoverable credentials.
    allow = None
    if user:
        allow = [cred.as_descriptor() for cred in user.credentials.all()]
    options = generate_authentication_options(rp_id="example.com", allow_credentials=allow)
    cache.set("auth_chal", options.challenge, timeout=300)
    return options_to_json(options)
```

```python
# server: complete authentication
from webauthn import verify_authentication_response

def login_complete(body):
    stored = Credential.objects.get(credential_id=base64url_decode(body["rawId"]))
    verification = verify_authentication_response(
        credential=body,
        expected_challenge=cache.get("auth_chal"),
        expected_rp_id="example.com",
        expected_origin="https://example.com",
        credential_public_key=stored.public_key,
        credential_current_sign_count=stored.sign_count,
        require_user_verification=True,
    )
    # Cloned-authenticator detection: the counter must move forward.
    if verification.new_sign_count <= stored.sign_count and stored.sign_count != 0:
        raise SecurityError("possible cloned authenticator")
    stored.sign_count = verification.new_sign_count
    stored.save(update_fields=["sign_count"])
    return stored.user
```

```javascript
import { startAuthentication } from "@simplewebauthn/browser";

const options = await fetch("/login/begin", { method: "POST" }).then((r) => r.json());
const assertion = await startAuthentication(options);   // user picks a passkey, verifies
const user = await fetch("/login/complete", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(assertion),
}).then((r) => r.json());
```

## Passkeys: Synced vs Device-Bound

The two ceremonies above work for any WebAuthn credential, including a hardware security key used as a second factor. What turned the protocol into a mainstream password replacement is a particular kind of credential with particular backup behavior -- and the distinction shapes how you design account recovery.

A **passkey** is simply a *discoverable* (resident) WebAuthn credential with good UX on top. Two flavors matter operationally:

- **Synced passkeys** are backed up and synchronized across a user's devices by a platform credential manager (iCloud Keychain, Google Password Manager, 1Password, etc.). They survive a lost phone -- the user signs in on a new device and the passkey is already there. This is what makes passkeys a *password replacement* and not just a hardware-key feature.
- **Device-bound credentials** never leave the authenticator (a FIDO2 security key, or a platform authenticator configured as device-bound). Higher assurance, but losing the device loses the credential -- so they need a registered backup.

Two UX wins fall out of discoverable credentials: **usernameless login** (the server sends no `allow_credentials`, and the authenticator offers the accounts it holds) and **conditional UI / autofill** (`startAuthentication({ ..., useBrowserAutofill: true })`), where passkeys appear in the username field's autofill dropdown.

## Security Properties & Gotchas

The cryptography gives you strong guarantees out of the box; deployments fail on the operational details around it. These are the points where real implementations go wrong.

- **Phishing resistance is the headline.** Because the assertion is bound to the origin and RP ID, a relayed credential is useless on the wrong domain. This is the one property passwords + OTP cannot match.
- **The sign counter is a weak signal.** It exists to detect cloned authenticators, but many platform authenticators and synced passkeys report `0` and never increment (a synced key lives on many devices by design). Treat a non-monotonic counter as suspicious only when the stored count is non-zero, as above -- do not hard-fail on `0`.
- **Account recovery is the real design problem.** A user who loses all authenticators must still get back in. Provide a recovery path (a second registered passkey, a recovery code, or an email/identity-proofing fallback) *before* you let anyone make a passkey their only factor -- otherwise you have built a lockout machine.
- **Don't require attestation for consumer apps.** Requesting `attestation="direct"` returns information that can de-anonymize the authenticator make/model and adds verification burden; `none` is the right default outside high-assurance/enterprise contexts.
- **RP ID scoping is a footgun.** Set the RP ID to the registrable domain (`example.com`), not a host (`app.example.com`), if you want the passkey to work across subdomains -- but never set it to a domain you do not control, or the browser rejects it.

In Django, the request/response handlers above slot directly into views (`py_webauthn` is framework-agnostic); store `Credential` rows in a model keyed by `credential_id`, and keep the per-ceremony challenge in the cache or session (never in a hidden form field, where it could be tampered with).

> **Key Takeaway:** WebAuthn replaces a phishable shared secret with a per-site key pair whose private half never leaves the user's authenticator. Both ceremonies reduce to "server issues a challenge, authenticator signs it, server verifies against the stored public key, bound to the origin." Use a maintained library for the crypto, make credentials *discoverable* to get passkeys, and design account recovery *first* -- the cryptography is the easy part; not locking users out is the hard part.

## Summary

Passwords fail because they are shared secrets: reusable, phishable, and leakable in a single breach, and even a TOTP second factor can be relayed in real time by an adversary-in-the-middle. WebAuthn replaces the shared secret with a per-site asymmetric key pair -- the private key never leaves the authenticator, the server stores only the public key, and every assertion is bound to the site's origin, which makes the protocol phishing-resistant by construction rather than by user vigilance.

The mental model is four parties: the authenticator holds the private key, the browser enforces origin and RP ID, and the relying party (your server) issues challenges and verifies signatures against the stored public key. Both ceremonies reduce to the same shape -- server issues a random challenge, authenticator signs over it, server verifies -- with registration creating the credential and authentication proving possession of it. The decision rules worth carrying forward:

- Use a maintained library (`py_webauthn`, `@simplewebauthn/browser`) for the COSE/CBOR and encoding plumbing; never hand-roll it.
- Set `resident_key=REQUIRED` to get discoverable credentials -- that is what makes a passkey, and what enables usernameless login and autofill.
- Scope the RP ID to the registrable domain, keep `user_id` opaque and stable, treat the sign counter as a weak signal, and default attestation to `none` for consumer apps.
- Design account recovery *before* letting a passkey become the only factor; the cryptography is the easy part, and not building a lockout machine is the hard part.

This closes Chapter 5: we have moved from designing API surfaces, through integration patterns and authentication, to removing the password from the login path entirely. Chapter 6 shifts from the shape of the interface to the systems behind it, beginning with **6.1 Scalability** -- how a backend keeps working as load grows.

*Last reviewed: 2026-06-08*

**Next:** [6.1 Scalability](../06-system-design/scalability.md)
