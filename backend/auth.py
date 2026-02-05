"""
Authentication and authorization utilities for the Pantry App.
Handles Cognito JWT token validation and user group checks.
"""

from typing import Optional, Dict, Any, List
from aws_lambda_powertools import Logger

logger = Logger(child=True)


def get_user_id_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract the user ID (sub claim) from the API Gateway event.

    When API Gateway uses a Cognito authorizer, the JWT claims are available
    in the request context under 'authorizer.claims'.

    Args:
        event: The Lambda event from API Gateway

    Returns:
        The user's unique ID (sub claim) or None if not authenticated
    """
    try:
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        user_id = claims.get("sub")
        if user_id:
            logger.info(f"Extracted user_id: {user_id}")
        return user_id
    except Exception as e:
        logger.exception("Error extracting user_id from event")
        return None


def get_user_groups(event: Dict[str, Any]) -> List[str]:
    """
    Extract the user's Cognito groups from the API Gateway event.

    Args:
        event: The Lambda event from API Gateway

    Returns:
        List of group names the user belongs to
    """
    try:
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        # Cognito groups are stored in the 'cognito:groups' claim as a comma-separated string
        groups_str = claims.get("cognito:groups", "")
        if groups_str:
            groups = [g.strip() for g in groups_str.split(",")]
            logger.info(f"User groups: {groups}")
            return groups
        return []
    except Exception as e:
        logger.exception("Error extracting user groups from event")
        return []


def is_admin(event: Dict[str, Any]) -> bool:
    """
    Check if the user is in the Admin group.

    Args:
        event: The Lambda event from API Gateway

    Returns:
        True if the user is an admin, False otherwise
    """
    groups = get_user_groups(event)
    return "Admin" in groups


def get_effective_user_id(event: Dict[str, Any], requested_user_id: Optional[str] = None) -> str:
    """
    Get the effective user ID for a request, considering admin privileges.

    - Regular users can only access their own data
    - Admins can access any user's data by specifying a user_id parameter
    - If no user_id is specified, returns the authenticated user's ID

    Args:
        event: The Lambda event from API Gateway
        requested_user_id: Optional user_id parameter from the request

    Returns:
        The effective user_id to use for data access

    Raises:
        PermissionError: If a non-admin user tries to access another user's data
    """
    authenticated_user_id = get_user_id_from_event(event)

    if not authenticated_user_id:
        raise PermissionError("User not authenticated")

    # If no specific user requested, use authenticated user
    if not requested_user_id:
        return authenticated_user_id

    # If requesting their own data, allow
    if requested_user_id == authenticated_user_id:
        return authenticated_user_id

    # If requesting another user's data, must be admin
    if is_admin(event):
        logger.info(f"Admin {authenticated_user_id} accessing data for user {requested_user_id}")
        return requested_user_id

    # Non-admin trying to access another user's data
    raise PermissionError(f"User {authenticated_user_id} is not authorized to access data for user {requested_user_id}")
