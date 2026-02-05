/**
 * ErrorMessage Component
 * Displays user-friendly error messages
 */

import React from 'react';
import { Alert, AlertIcon, AlertDescription } from '@chakra-ui/react';

/**
 * Map Cognito error codes to user-friendly messages
 */
const errorMessages = {
  UserNotFoundException: 'Invalid email or password',
  NotAuthorizedException: 'Invalid email or password',
  UserNotConfirmedException: 'Please confirm your email before logging in',
  UsernameExistsException: 'An account with this email already exists',
  InvalidPasswordException: 'Password does not meet requirements',
  CodeMismatchException: 'Invalid verification code',
  ExpiredCodeException: 'Verification code has expired',
  LimitExceededException: 'Too many attempts. Please try again later',
  InvalidParameterException: 'Invalid input. Please check your information'
};

/**
 * Get user-friendly error message
 */
function getErrorMessage(error) {
  if (typeof error === 'string') {
    // Check if it's a known error code
    return errorMessages[error] || error;
  }

  if (error?.code) {
    return errorMessages[error.code] || error.message || 'An error occurred';
  }

  return error?.message || 'An unexpected error occurred';
}

export default function ErrorMessage({ error, onClose }) {
  if (!error) return null;

  return (
    <Alert status="error" borderRadius="md" mb={4}>
      <AlertIcon />
      <AlertDescription>{getErrorMessage(error)}</AlertDescription>
    </Alert>
  );
}
