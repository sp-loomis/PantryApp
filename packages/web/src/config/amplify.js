/**
 * AWS Amplify Configuration
 * Configure Amplify with Cognito settings
 */

import { Amplify } from 'aws-amplify';

const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
      region: import.meta.env.VITE_AWS_REGION || 'us-east-2',
      loginWith: {
        email: true
      }
    }
  }
};

/**
 * Initialize Amplify with configuration
 */
export function configureAmplify() {
  Amplify.configure(amplifyConfig);
}

export default amplifyConfig;
