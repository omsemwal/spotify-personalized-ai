"""
Minimal service-identity + subject-scope authentication for the pilot.
Spec ref: §5.4 "Attach subject scope... to every event", §5.5 Security:
"Every read and write must bind to authenticated subject and service identities."

Production would verify a signed workload token (e.g. mTLS + JWT) issued by the
platform's identity provider. For the pilot, this validates a bearer token
against a service registry and extracts the subject claim — swap
`verify_service_token` for the real IdP call when integrating.
"""
import os

from fastapi import Header, HTTPException, status

# Pilot-only static registry: {token: service_name}. Replace with real IdP integration.
_SERVICE_TOKENS = {
    os.getenv("INGESTION_SERVICE_TOKEN", "dev-ingestion-token"): "trusted_surface_gateway",
}


def verify_service_token(authorization: str = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "error_code": "unauthenticated", "message": "Missing or malformed bearer token"
        })
    token = authorization.removeprefix("Bearer ").strip()
    service_name = _SERVICE_TOKENS.get(token)
    if not service_name:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "error_code": "unauthenticated", "message": "Unknown service token"
        })
    return service_name
