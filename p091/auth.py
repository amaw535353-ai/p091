"""Cryptographic identities for the synthetic lab; no request-supplied identity."""

from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException


@dataclass(frozen=True)
class Principal:
    sub: str
    tenant: str
    actor_type: str
    scopes: frozenset[str]


class Authenticator:
    """Offline RSA issuer or live trusted-JWKS verifier, never both at once.

    The offline issuer is a deliberately synthetic identity provider and is not
    Keycloak. Ephemeral signing material is never written into the repository.
    Live JWKS is fetched for each decision so issuer outages deny access. This
    availability choice does not replace token introspection/session revocation.
    """

    def __init__(self, settings: Any, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=5, follow_redirects=False)
        self.private_key = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            if settings.mode == "offline"
            else None
        )
        self._revoked: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue_lab_token(
        self,
        sub: str,
        tenant: str,
        actor_type: str = "human",
        scopes: str = "read",
        overrides: dict[str, Any] | None = None,
    ) -> str:
        """Test fixture only. HTTP login must separately restrict synthetic users."""
        if self.settings.mode != "offline" or self.private_key is None:
            raise HTTPException(404, "Synthetic login unavailable")
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": sub,
            "tenant": tenant,
            "actor_type": actor_type,
            "scope": scopes,
            "iss": self.settings.issuer,
            "aud": self.settings.audience,
            "iat": now,
            "nbf": now,
            "exp": now + 900,
            "jti": str(uuid4()),
        }
        claims.update(overrides or {})
        return jwt.encode(
            claims, self.private_key, algorithm="RS256", headers={"kid": "offline-lab"}
        )

    def _key(self, token: str) -> Any:
        if self.settings.mode == "offline":
            if self.private_key is None:
                raise HTTPException(503, "Identity service unavailable")
            return self.private_key.public_key()
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise HTTPException(401, "Invalid credentials")
            url = self.settings.jwks_url or (
                self.settings.issuer.rstrip("/") + "/protocol/openid-connect/certs"
            )
            response = self.client.get(url)
            response.raise_for_status()
            keys = response.json()["keys"]
            if not isinstance(keys, list) or len(keys) > 100 or not all(
                isinstance(key, dict) for key in keys
            ):
                raise ValueError("Invalid key set")
            matching = [key for key in keys if key.get("kid") == header["kid"]]
            if len(matching) != 1:
                raise HTTPException(401, "Invalid credentials")
            key = matching[0]
            if key.get("kty") != "RSA" or key.get("use", "sig") != "sig":
                raise HTTPException(401, "Invalid credentials")
            if key.get("alg", "RS256") != "RS256":
                raise HTTPException(401, "Invalid credentials")
            return jwt.PyJWK.from_dict(key, algorithm="RS256").key
        except HTTPException:
            raise
        except jwt.InvalidTokenError as error:
            raise HTTPException(401, "Invalid credentials") from error
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise HTTPException(503, "Identity service unavailable") from error

    def _validated_claims(self, token: str) -> dict[str, Any]:
        """Authenticate before consulting any token-supplied revocation identity."""
        if not isinstance(token, str) or not 1 <= len(token) <= 8192:
            raise HTTPException(401, "Invalid credentials")
        try:
            claims = jwt.decode(
                token,
                self._key(token),
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.audience,
                leeway=0,
                options={
                    "require": [
                        "exp", "iat", "iss", "aud", "sub", "jti",
                        "tenant", "actor_type", "scope",
                    ]
                },
            )
            # NumericDate strings and booleans are rejected even where a JWT
            # library accepts coercion. JWT claims cannot supply policy groups.
            for name in ("exp", "iat", "nbf"):
                if name in claims and (
                    isinstance(claims[name], bool) or not isinstance(claims[name], (int, float))
                ):
                    raise ValueError("Invalid date")
            for name in ("sub", "tenant"):
                if not isinstance(claims[name], str) or not re.fullmatch(
                    r"[A-Za-z0-9_.-]{1,128}", claims[name]
                ):
                    raise ValueError("Invalid identifier")
            if claims["actor_type"] not in ("human", "service"):
                raise ValueError("Invalid actor")
            if not isinstance(claims["scope"], str) or len(claims["scope"]) > 1024:
                raise ValueError("Invalid scope")
            if not isinstance(claims["jti"], str) or not 1 <= len(claims["jti"]) <= 128:
                raise ValueError("Invalid token identifier")
            return claims
        except HTTPException:
            raise
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError, OverflowError) as error:
            raise HTTPException(401, "Invalid credentials") from error

    @staticmethod
    def _revocation_identity(claims: dict[str, Any]) -> str:
        # Same authenticated JWT identity may have several accepted Base64URL
        # signature spellings. Raw serialized-token hashes do not revoke those
        # variants. The issuer+jti identity is stable after signature validation.
        return hashlib.sha256((claims["iss"] + "\x00" + claims["jti"]).encode()).hexdigest()

    def _ensure_active(self, claims: dict[str, Any]) -> None:
        fingerprint = self._revocation_identity(claims)
        now = time.time()
        with self._lock:
            self._revoked = {k: exp for k, exp in self._revoked.items() if exp > now}
            if fingerprint in self._revoked:
                raise HTTPException(401, "Invalid credentials")

    def verify(self, token: str) -> Principal:
        claims = self._validated_claims(token)
        self._ensure_active(claims)
        return Principal(
            sub=claims["sub"],
            tenant=claims["tenant"],
            actor_type=claims["actor_type"],
            scopes=frozenset(claims["scope"].split()),
        )

    def revoke(self, token: str) -> None:
        """Revoke in this process; deployments need a durable revocation store."""
        claims = self._validated_claims(token)
        self._ensure_active(claims)
        fingerprint = self._revocation_identity(claims)
        with self._lock:
            self._revoked[fingerprint] = float(claims["exp"])
