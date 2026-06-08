import base64
import hashlib
import json


def verify_assertion(assertion, *, expected_challenge, expected_rp_id,
                     expected_origin, stored_public_key, stored_sign_count,
                     verify_signature):
    """Verify a (simplified) WebAuthn authentication assertion.

    `verify_signature(public_key, signed_bytes, signature) -> bool` is provided
    for you (real signature checking is delegated to a crypto library). Your job
    is the surrounding validation that makes WebAuthn phishing-resistant.

    Return the new sign count on success; raise ValueError on any failure.
    """
    # TODO:
    #   1. Decode assertion["clientDataJSON"]; assert type == "webauthn.get",
    #      challenge == expected_challenge, and origin == expected_origin.
    #   2. Assert the authenticatorData's RP ID hash equals
    #      hashlib.sha256(expected_rp_id.encode()).digest().
    #   3. signed_bytes = authenticatorData + sha256(clientDataJSON); call
    #      verify_signature(stored_public_key, signed_bytes, assertion["signature"]).
    #   4. Parse the new sign count from authenticatorData; reject if it is not
    #      greater than stored_sign_count (unless stored_sign_count == 0).
    #   5. Return the new sign count.
    raise NotImplementedError


if __name__ == "__main__":
    # Implement verify_assertion(), then exercise the challenge / origin /
    # RP-ID-hash / signature / counter-monotonicity checks with crafted inputs.
    print("Implement verify_assertion() and test its five validation steps.")
