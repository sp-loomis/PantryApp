/**
 * Validation Utilities
 * Client-side validation for forms
 */

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean|string} True if valid, error message if invalid
 */
export function validateEmail(email) {
  if (!email) {
    return 'Email is required';
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return 'Please enter a valid email address';
  }

  return true;
}

/**
 * Validate password strength
 * Must meet Cognito requirements: 8+ chars, uppercase, lowercase, numbers
 * @param {string} password - Password to validate
 * @returns {boolean|string} True if valid, error message if invalid
 */
export function validatePassword(password) {
  if (!password) {
    return 'Password is required';
  }

  if (password.length < 8) {
    return 'Password must be at least 8 characters';
  }

  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter';
  }

  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter';
  }

  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number';
  }

  return true;
}

/**
 * Validate password confirmation
 * @param {string} password - Original password
 * @param {string} confirmPassword - Confirmation password
 * @returns {boolean|string} True if valid, error message if invalid
 */
export function validatePasswordConfirmation(password, confirmPassword) {
  if (!confirmPassword) {
    return 'Please confirm your password';
  }

  if (password !== confirmPassword) {
    return 'Passwords do not match';
  }

  return true;
}

/**
 * Validate verification code
 * @param {string} code - Verification code
 * @returns {boolean|string} True if valid, error message if invalid
 */
export function validateVerificationCode(code) {
  if (!code) {
    return 'Verification code is required';
  }

  if (!/^\d{6}$/.test(code)) {
    return 'Verification code must be 6 digits';
  }

  return true;
}
