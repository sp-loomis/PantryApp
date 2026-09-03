/**
 * Error Message Component
 *
 * Displays user-friendly error messages.
 * Maps AWS Cognito error codes to readable messages.
 */

import { Alert, AlertIcon, AlertDescription } from '@chakra-ui/react';

/**
 * Map Cognito error codes to user-friendly messages
 */
const ERROR_MESSAGES = {
  'UserNotFoundException': 'Invalid email or password',
  'NotAuthorizedException': 'Invalid email or password',
  'UsernameExistsException': 'An account with this email already exists',
  'InvalidPasswordException': 'Password does not meet requirements',
  'CodeMismatchException': 'Invalid verification code',
  'ExpiredCodeException': 'Verification code has expired',
  'LimitExceededException': 'Too many attempts. Please try again later',
  'InvalidParameterException': 'Invalid input. Please check your entries',
  'UserNotConfirmedException': 'Please verify your email before signing in'
};

/**
 * Get user-friendly error message
 */
/**
 * Fallback messages for backend API errors (ApiError) by HTTP status, used only
 * when the backend didn't supply a specific message.
 */
const API_STATUS_MESSAGES = {
  401: 'Your session has expired. Please sign in again.',
  403: 'You do not have permission to do that.',
  404: 'Not found.',
  500: 'Something went wrong. Please try again.'
};

function getUserFriendlyMessage(error) {
  if (!error) return null;

  // If error is a string, return it directly
  if (typeof error === 'string') {
    return error;
  }

  // Backend API errors: the backend's own message is user-facing (e.g.
  // "Location not found"); fall back to a status-based message if absent.
  if (error.name === 'ApiError') {
    return error.message || API_STATUS_MESSAGES[error.status] || 'Request failed. Please try again';
  }

  // Check for Cognito error code
  if (error.name && ERROR_MESSAGES[error.name]) {
    return ERROR_MESSAGES[error.name];
  }

  // Check for error message
  if (error.message) {
    // Check if message contains a known error code
    for (const [code, message] of Object.entries(ERROR_MESSAGES)) {
      if (error.message.includes(code)) {
        return message;
      }
    }
    return error.message;
  }

  return 'An error occurred. Please try again';
}

/**
 * ErrorMessage Component
 */
export default function ErrorMessage({ error }) {
  if (!error) return null;

  const message = getUserFriendlyMessage(error);

  return (
    <Alert status="error" borderRadius="md" mb={4}>
      <AlertIcon />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
