/**
 * Shared Package - Platform-agnostic business logic
 * Export all services, hooks, and utilities
 */

// Services
export {
  signUpUser,
  confirmUserSignUp,
  signInUser,
  signOutUser,
  getCurrentAuthUser
} from './services/authService.js';

// Hooks
export { useAuth } from './hooks/useAuth.js';

// Utilities
export {
  validateEmail,
  validatePassword,
  validatePasswordConfirmation,
  validateVerificationCode
} from './utils/validation.js';
