/**
 * useAuth Hook
 * Custom hook for authentication state management
 * Note: This is a shared hook that can be used in both web and mobile
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
 * @returns {Object} Auth state and methods
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check for existing session on mount
  useEffect(() => {
    checkAuthState();
  }, []);

  const checkAuthState = async () => {
    setIsLoading(true);
    const result = await getCurrentAuthUser();

    if (result.success && result.user) {
      setUser({
        email: result.user.username,
        userId: result.user.userId,
        emailVerified: true
      });
      setIsAuthenticated(true);
    } else {
      setUser(null);
      setIsAuthenticated(false);
    }

    setIsLoading(false);
  };

  const signup = useCallback(async (email, password) => {
    setIsLoading(true);
    setError(null);

    const result = await signUpUser(email, password);

    if (result.success) {
      setIsLoading(false);
      return { success: true, userId: result.userId };
    } else {
      setError(result.error);
      setIsLoading(false);
      return { success: false, error: result.error };
    }
  }, []);

  const confirmSignup = useCallback(async (email, code) => {
    setIsLoading(true);
    setError(null);

    const result = await confirmUserSignUp(email, code);

    if (result.success) {
      setIsLoading(false);
      return { success: true };
    } else {
      setError(result.error);
      setIsLoading(false);
      return { success: false, error: result.error };
    }
  }, []);

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    setError(null);

    const result = await signInUser(email, password);

    if (result.success) {
      // Refresh auth state after successful login
      await checkAuthState();
      return { success: true };
    } else {
      setError(result.error);
      setIsLoading(false);
      return { success: false, error: result.error };
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const result = await signOutUser();

    if (result.success) {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      return { success: true };
    } else {
      setError(result.error);
      setIsLoading(false);
      return { success: false, error: result.error };
    }
  }, []);

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
    refreshAuth: checkAuthState
  };
}
