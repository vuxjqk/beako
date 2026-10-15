from dataclasses import dataclass

import requests
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from src.core.config import settings

# Reuse connections to Google's certs endpoint
_session = requests.Session()


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str
    picture: str | None


class GoogleTokenError(Exception):
    """The ID token is invalid, expired, for another audience or has no verified email."""


class GoogleUnavailableError(Exception):
    """Google sign-in isn't configured or Google's certs couldn't be fetched."""


def verify_google_id_token(token: str) -> GoogleIdentity:
    # Without an audience google-auth accepts tokens issued to any app, so refuse instead
    if not settings.google_client_ids:
        raise GoogleUnavailableError("GOOGLE_CLIENT_ID is not configured")
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(session=_session),
            audience=settings.google_client_ids,
            clock_skew_in_seconds=10,
        )
    except google_exceptions.TransportError as e:
        raise GoogleUnavailableError(str(e)) from e
    except (ValueError, google_exceptions.GoogleAuthError) as e:
        raise GoogleTokenError(str(e)) from e

    email = claims.get("email")
    if not email or not claims.get("email_verified"):
        raise GoogleTokenError("Google account email is not verified")
    email = email.lower()
    return GoogleIdentity(
        sub=claims["sub"],
        email=email,
        name=(claims.get("name") or email.split("@")[0])[:255],
        picture=claims.get("picture"),
    )
