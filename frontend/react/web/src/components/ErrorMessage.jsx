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
function getUserFriendlyMessage(error) {
  if (!error) return null;

  // If error is a string, return it directly
  if (typeof error === 'string') {
    return error;
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
export default function ErrorMessage({ error, onClose }) {
  if (!error) return null;

  const message = getUserFriendlyMessage(error);

  return (
    <Alert status="error" borderRadius="md" mb={4}>
      <AlertIcon />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
