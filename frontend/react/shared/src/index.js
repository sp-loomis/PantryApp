/**
 * @pantry-app/shared
 *
 * Platform-agnostic business logic for Pantry App
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

// Utils
export {
  validateEmail,
  validatePassword,
  validatePasswordConfirmation,
  validateVerificationCode
} from './utils/validation.js';
