/**
 * Authentication Context
 *
 * Provides authentication state and methods to the entire app.
 * Uses the useAuth hook from @pantry-app/shared.
 */

import { createContext, useContext } from 'react';
import { useAuth } from '@pantry-app/shared';

const AuthContext = createContext(null);

/**
 * Auth Provider Component
 * Wraps the app to provide authentication state
 */
export function AuthProvider({ children }) {
  const auth = useAuth();

  return (
    <AuthContext.Provider value={auth}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access authentication context
 * @returns {Object} Authentication state and methods
 */
export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }

  return context;
}
