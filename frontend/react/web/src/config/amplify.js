/**
 * AWS Amplify Configuration
 *
 * Configures Amplify for AWS Cognito authentication.
 * Environment variables are loaded from .env file.
 */

import { Amplify } from 'aws-amplify';

const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
      region: import.meta.env.VITE_AWS_REGION || 'us-east-2',
      loginWith: {
        email: true
      },
      signUpVerificationMethod: 'code',
      userAttributes: {
        email: {
          required: true
        }
      },
      passwordFormat: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireNumbers: true,
        requireSpecialCharacters: false
      }
    }
  }
};

/**
 * Initialize Amplify configuration
 * Call this once at app startup
 */
export function configureAmplify() {
  try {
    Amplify.configure(amplifyConfig);
    console.log('Amplify configured successfully');
  } catch (error) {
    console.error('Failed to configure Amplify:', error);
    throw error;
  }
}

export default amplifyConfig;
