"""
Authentication module for Pantry CLI.
Handles AWS Cognito authentication and token management.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict

import boto3
from botocore.exceptions import ClientError


# Token storage location
TOKEN_FILE = Path.home() / ".pantry" / "tokens.json"


def ensure_token_dir():
    """Ensure the token directory exists."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)


def save_tokens(tokens: Dict[str, any]):
    """Save authentication tokens to disk."""
    ensure_token_dir()
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)
    # Set restrictive permissions
    TOKEN_FILE.chmod(0o600)


def load_tokens() -> Optional[Dict[str, any]]:
    """Load authentication tokens from disk."""
    if not TOKEN_FILE.exists():
        return None

    try:
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def clear_tokens():
    """Clear stored authentication tokens."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def get_cognito_client():
    """Get a Cognito Identity Provider client."""
    return boto3.client('cognito-idp')


def login(username: str, password: str, user_pool_id: str, client_id: str) -> Dict[str, str]:
    """
    Authenticate with AWS Cognito using email and password.

    Args:
        username: The user's email address (used as username in Cognito)
        password: The user's password
        user_pool_id: The Cognito User Pool ID
        client_id: The Cognito App Client ID

    Returns:
        Dictionary containing tokens (IdToken, AccessToken, RefreshToken)

    Raises:
        Exception: If authentication fails
    """
    cognito = get_cognito_client()

    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )

        auth_result = response['AuthenticationResult']
        tokens = {
            'IdToken': auth_result['IdToken'],
            'AccessToken': auth_result['AccessToken'],
            'RefreshToken': auth_result['RefreshToken'],
            'ExpiresIn': auth_result['ExpiresIn'],
            'TokenType': auth_result['TokenType'],
            'timestamp': int(time.time())
        }

        save_tokens(tokens)
        return tokens

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NotAuthorizedException':
            raise Exception("Invalid username or password")
        elif error_code == 'UserNotFoundException':
            raise Exception("User not found")
        elif error_code == 'UserNotConfirmedException':
            raise Exception("User email not confirmed")
        else:
            raise Exception(f"Authentication failed: {e.response['Error']['Message']}")


def refresh_tokens(refresh_token: str, client_id: str) -> Dict[str, str]:
    """
    Refresh authentication tokens using a refresh token.

    Args:
        refresh_token: The refresh token
        client_id: The Cognito App Client ID

    Returns:
        Dictionary containing new tokens

    Raises:
        Exception: If token refresh fails
    """
    cognito = get_cognito_client()

    try:
        response = cognito.initiate_auth(
            ClientId=client_id,
            AuthFlow='REFRESH_TOKEN_AUTH',
            AuthParameters={
                'REFRESH_TOKEN': refresh_token
            }
        )

        auth_result = response['AuthenticationResult']
        tokens = load_tokens() or {}
        tokens.update({
            'IdToken': auth_result['IdToken'],
            'AccessToken': auth_result['AccessToken'],
            'ExpiresIn': auth_result['ExpiresIn'],
            'timestamp': int(time.time())
        })

        save_tokens(tokens)
        return tokens

    except ClientError as e:
        clear_tokens()
        raise Exception(f"Token refresh failed: {e.response['Error']['Message']}")


def get_valid_id_token(client_id: str) -> Optional[str]:
    """
    Get a valid ID token, refreshing if necessary.

    Args:
        client_id: The Cognito App Client ID

    Returns:
        Valid ID token or None if not authenticated
    """
    tokens = load_tokens()
    if not tokens:
        return None

    # Check if token is expired (with 5 minute buffer)
    timestamp = tokens.get('timestamp', 0)
    expires_in = tokens.get('ExpiresIn', 0)
    current_time = int(time.time())

    if current_time - timestamp < expires_in - 300:  # 5 minute buffer
        return tokens['IdToken']

    # Token expired, try to refresh
    refresh_token = tokens.get('RefreshToken')
    if not refresh_token:
        clear_tokens()
        return None

    try:
        new_tokens = refresh_tokens(refresh_token, client_id)
        return new_tokens['IdToken']
    except Exception:
        clear_tokens()
        return None


def is_logged_in() -> bool:
    """Check if the user is currently logged in."""
    tokens = load_tokens()
    return tokens is not None and 'IdToken' in tokens


def sign_up(email: str, password: str, user_pool_id: str, client_id: str):
    """
    Sign up a new user.

    Args:
        email: The user's email address (used as username)
        password: The user's password
        user_pool_id: The Cognito User Pool ID
        client_id: The Cognito App Client ID

    Returns:
        Dictionary with signup result

    Raises:
        Exception: If signup fails
    """
    cognito = get_cognito_client()

    try:
        response = cognito.sign_up(
            ClientId=client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {'Name': 'email', 'Value': email}
            ]
        )

        return {
            'UserConfirmed': response['UserConfirmed'],
            'UserSub': response['UserSub']
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'UsernameExistsException':
            raise Exception("Email already exists")
        elif error_code == 'InvalidPasswordException':
            raise Exception("Password does not meet requirements")
        elif error_code == 'InvalidParameterException':
            raise Exception(f"Invalid parameter: {e.response['Error']['Message']}")
        else:
            raise Exception(f"Signup failed: {e.response['Error']['Message']}")


def confirm_signup(email: str, confirmation_code: str, client_id: str):
    """
    Confirm user signup with verification code.

    Args:
        email: The user's email address
        confirmation_code: The verification code sent to email
        client_id: The Cognito App Client ID

    Raises:
        Exception: If confirmation fails
    """
    cognito = get_cognito_client()

    try:
        cognito.confirm_sign_up(
            ClientId=client_id,
            Username=email,
            ConfirmationCode=confirmation_code
        )

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'CodeMismatchException':
            raise Exception("Invalid verification code")
        elif error_code == 'ExpiredCodeException':
            raise Exception("Verification code has expired")
        else:
            raise Exception(f"Confirmation failed: {e.response['Error']['Message']}")
