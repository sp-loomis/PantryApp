/**
 * Authentication Service
 * Provides platform-agnostic authentication operations using AWS Amplify
 */

import { signUp, confirmSignUp, signIn, signOut, getCurrentUser } from 'aws-amplify/auth';

/**
 * Sign up a new user
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} Signup result with userId and confirmation status
 */
export async function signUpUser(email, password) {
  try {
    const { userId, isSignUpComplete, nextStep } = await signUp({
      username: email,
      password,
      options: {
        userAttributes: {
          email
        }
      }
    });

    return {
      success: true,
      userId,
      isSignUpComplete,
      nextStep
    };
  } catch (error) {
    return {
      success: false,
      error: error.message || 'Signup failed',
      code: error.name
    };
  }
}

/**
 * Confirm user signup with verification code
 * @param {string} email - User email
 * @param {string} code - Verification code
 * @returns {Promise<Object>} Confirmation result
 */
export async function confirmUserSignUp(email, code) {
  try {
    const { isSignUpComplete, nextStep } = await confirmSignUp({
      username: email,
      confirmationCode: code
    });

    return {
      success: true,
      isSignUpComplete,
      nextStep
    };
  } catch (error) {
    return {
      success: false,
      error: error.message || 'Confirmation failed',
      code: error.name
    };
  }
}

/**
 * Sign in a user
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<Object>} Sign in result
 */
export async function signInUser(email, password) {
  try {
    const { isSignedIn, nextStep } = await signIn({
      username: email,
      password
    });

    return {
      success: true,
      isSignedIn,
      nextStep
    };
  } catch (error) {
    return {
      success: false,
      error: error.message || 'Sign in failed',
      code: error.name
    };
  }
}

/**
 * Sign out the current user
 * @returns {Promise<Object>} Sign out result
 */
export async function signOutUser() {
  try {
    await signOut();
    return {
      success: true
    };
  } catch (error) {
    return {
      success: false,
      error: error.message || 'Sign out failed',
      code: error.name
    };
  }
}

/**
 * Get the current authenticated user
 * @returns {Promise<Object>} Current user or null
 */
export async function getCurrentAuthUser() {
  try {
    const user = await getCurrentUser();
    return {
      success: true,
      user: {
        userId: user.userId,
        username: user.username,
        signInDetails: user.signInDetails
      }
    };
  } catch (error) {
    return {
      success: false,
      user: null,
      error: error.message,
      code: error.name
    };
  }
}
