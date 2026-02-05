/**
 * useAuth Hook
 *
 * Custom React hook for authentication state management.
 * This hook can be used across web and mobile (React Native) apps.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  signUpUser,
  confirmUserSignUp,
  signInUser,
  signOutUser,
  getCurrentAuthUser
} from '../services/authService.js';

/**
 * Authentication hook
 * @returns {Object} Authentication state and methods
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check if user is already authenticated on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  /**
   * Check current authentication status
   */
  const checkAuthStatus = async () => {
    try {
      setIsLoading(true);
      const currentUser = await getCurrentAuthUser();

      if (currentUser) {
        setUser(currentUser);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (err) {
      console.error('Auth status check error:', err);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Sign up a new user
   */
  const signup = useCallback(async (email, password) => {
    try {
      setIsLoading(true);
      setError(null);

      const result = await signUpUser(email, password);
      return result;
    } catch (err) {
      setError(err.message || 'Signup failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Confirm user signup with verification code
   */
  const confirmSignup = useCallback(async (email, code) => {
    try {
      setIsLoading(true);
      setError(null);

      const result = await confirmUserSignUp(email, code);
      return result;
    } catch (err) {
      setError(err.message || 'Confirmation failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Sign in user
   */
  const login = useCallback(async (email, password) => {
    try {
      setIsLoading(true);
      setError(null);

      await signInUser(email, password);

      // Get user info after successful login
      const currentUser = await getCurrentAuthUser();
      setUser(currentUser);
      setIsAuthenticated(true);

      return currentUser;
    } catch (err) {
      setError(err.message || 'Login failed');
      setUser(null);
      setIsAuthenticated(false);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Sign out user
   */
  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      await signOutUser();
      setUser(null);
      setIsAuthenticated(false);
    } catch (err) {
      setError(err.message || 'Logout failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Clear error message
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    signup,
    confirmSignup,
    login,
    logout,
    clearError,
    checkAuthStatus
  };
}
