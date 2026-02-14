/**
 * Authentication Service
 *
 * Platform-agnostic AWS Amplify authentication operations.
 * Works on both web and mobile platforms.
 */

import { signUp, confirmSignUp, signIn, signOut, getCurrentUser } from 'aws-amplify/auth';

/**
 * Sign up a new user with email and password
 * @param {string} email - User's email address
 * @param {string} password - User's password
 * @returns {Promise<Object>} Signup result with userId and confirmation status
 * @throws {Error} If signup fails
 */
export async function signUpUser(email, password) {
  try {
    const { userId, isSignUpComplete, nextStep } = await signUp({
      username: email,
      password,
      options: {
        userAttributes: {
          email
        },
        autoSignIn: false
      }
    });

    return {
      userId,
      isSignUpComplete,
      nextStep
    };
  } catch (error) {
    console.error('Signup error:', error);
    throw error;
  }
}

/**
 * Confirm user signup with verification code
 * @param {string} email - User's email address
 * @param {string} code - Verification code from email
 * @returns {Promise<Object>} Confirmation result
 * @throws {Error} If confirmation fails
 */
export async function confirmUserSignUp(email, code) {
  try {
    const result = await confirmSignUp({
      username: email,
      confirmationCode: code
    });

    return result;
  } catch (error) {
    console.error('Confirmation error:', error);
    throw error;
  }
}

/**
 * Sign in user with email and password
 * @param {string} email - User's email address
 * @param {string} password - User's password
 * @returns {Promise<Object>} Sign in result
 * @throws {Error} If sign in fails
 */
export async function signInUser(email, password) {
  try {
    const { isSignedIn, nextStep } = await signIn({
      username: email,
      password
    });

    return {
      isSignedIn,
      nextStep
    };
  } catch (error) {
    console.error('Sign in error:', error);
    throw error;
  }
}

/**
 * Sign out the current user
 * @returns {Promise<void>}
 * @throws {Error} If sign out fails
 */
export async function signOutUser() {
  try {
    await signOut();
  } catch (error) {
    console.error('Sign out error:', error);
    throw error;
  }
}

/**
 * Get the current authenticated user
 * @returns {Promise<Object|null>} User object or null if not authenticated
 */
export async function getCurrentAuthUser() {
  try {
    const user = await getCurrentUser();
    return {
      userId: user.userId,
      email: user.signInDetails?.loginId || user.username
    };
  } catch (error) {
    // User not authenticated
    return null;
  }
}
