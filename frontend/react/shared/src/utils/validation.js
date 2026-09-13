/**
 * Validation Utilities
 *
 * Form validation functions for authentication.
 * Returns error messages or null if valid.
 */

/**
 * Validate email address format
 * @param {string} email - Email address to validate
 * @returns {string|null} Error message or null if valid
 */
export function validateEmail(email) {
  if (!email) {
    return 'Email is required';
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return 'Please enter a valid email address';
  }

  return null;
}

/**
 * Validate password strength
 * @param {string} password - Password to validate
 * @returns {string|null} Error message or null if valid
 */
export function validatePassword(password) {
  if (!password) {
    return 'Password is required';
  }

  if (password.length < 8) {
    return 'Password must be at least 8 characters';
  }

  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter';
  }

  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter';
  }

  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number';
  }

  return null;
}

/**
 * Validate password confirmation matches
 * @param {string} password - Original password
 * @param {string} confirmPassword - Confirmation password
 * @returns {string|null} Error message or null if valid
 */
export function validatePasswordConfirmation(password, confirmPassword) {
  if (!confirmPassword) {
    return 'Please confirm your password';
  }

  if (password !== confirmPassword) {
    return 'Passwords do not match';
  }

  return null;
}

/**
 * Validate verification code format
 * @param {string} code - Verification code to validate
 * @returns {string|null} Error message or null if valid
 */
export function validateVerificationCode(code) {
  if (!code) {
    return 'Verification code is required';
  }

  if (!/^\d{6}$/.test(code)) {
    return 'Verification code must be 6 digits';
  }

  return null;
}

/**
 * Validate an inventory item name
 * @param {string} name
 * @returns {string|null} Error message or null if valid
 */
export function validateItemName(name) {
  if (!name || !name.trim()) {
    return 'Item name is required';
  }
  return null;
}

/**
 * Validate a storage location name
 * @param {string} name
 * @returns {string|null} Error message or null if valid
 */
export function validateLocationName(name) {
  if (!name || !name.trim()) {
    return 'Location name is required';
  }
  return null;
}

/**
 * Validate a task name
 * @param {string} name
 * @returns {string|null} Error message or null if valid
 */
export function validateTaskName(name) {
  if (!name || !name.trim()) {
    return 'Task name is required';
  }
  return null;
}

/**
 * Validate a task's recurrence rule.
 * @param {{recurrence_type?: string, recurrence_interval?: number}} rule
 * @returns {string|null} Error message or null if valid
 */
export function validateRecurrence({ recurrence_type = 'none', recurrence_interval } = {}) {
  const allowed = ['none', 'daily', 'weekly', 'interval'];
  if (!allowed.includes(recurrence_type)) {
    return 'Invalid recurrence type';
  }
  if (recurrence_type === 'interval') {
    if (!Number.isInteger(recurrence_interval) || recurrence_interval < 1) {
      return 'Repeat interval must be a whole number of days (at least 1)';
    }
  }
  return null;
}

/**
 * Validate a report name.
 * @param {string} name
 * @returns {string|null} Error message or null if valid
 */
export function validateReportName(name) {
  if (!name || !name.trim()) {
    return 'Report name is required';
  }
  return null;
}

/**
 * Validate a report schedule (mirrors backend schedules.validate_schedule).
 * @param {{frequency?: string, time_of_day?: string, weekday?: number, day_of_month?: number}} schedule
 * @returns {string|null} Error message or null if valid
 */
export function validateSchedule({ frequency, time_of_day, weekday, day_of_month } = {}) {
  const allowed = ['daily', 'weekly', 'monthly'];
  if (!allowed.includes(frequency)) {
    return 'Choose a report frequency';
  }
  if (time_of_day && !/^([01]\d|2[0-3]):[0-5]\d$/.test(time_of_day)) {
    return 'Time of day must be HH:MM (24-hour)';
  }
  if (frequency === 'weekly' && !(Number.isInteger(weekday) && weekday >= 0 && weekday <= 6)) {
    return 'Choose a day of the week';
  }
  if (frequency === 'monthly' && !(Number.isInteger(day_of_month) && day_of_month >= 1 && day_of_month <= 28)) {
    return 'Choose a day of the month (1-28)';
  }
  return null;
}
