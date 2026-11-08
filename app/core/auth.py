
import httpx

from app.core.config import SUPABASE_URL, SUPABASE_ANON_KEY


class InvalidAccessToken(Exception):
    pass


class AuthProviderUnavailable(Exception):
    pass


def verify_supabase_access_token(access_token: str) -> str:
    if not access_token or not access_token.strip():
        raise InvalidAccessToken("Missing access token")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise AuthProviderUnavailable(
            "Supabase authentication is not configured"
        )

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {access_token.strip()}",
                },
            )

    except httpx.RequestError as exc:
        raise AuthProviderUnavailable(
            "Unable to reach Supabase Auth"
        ) from exc

    if response.status_code in (400, 401, 403):
        raise InvalidAccessToken("Invalid or expired access token")

    if response.status_code != 200:
        raise AuthProviderUnavailable(
            "Supabase Auth returned an unexpected response"
        )

    try:
        user_data = response.json()
        user_id = user_data.get("id")

        if not isinstance(user_id, str) or not user_id.strip():
            raise AuthProviderUnavailable(
                "Supabase Auth returned an invalid user response"
            )

        return user_id

    except (ValueError, AttributeError) as exc:
        raise AuthProviderUnavailable(
            "Invalid response from Supabase Auth"
        ) from exc
