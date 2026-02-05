# @pantry-app/shared

Platform-agnostic business logic for Pantry App authentication.

## Purpose

This package contains reusable authentication logic that can be shared across web and mobile applications:

- **Services**: AWS Amplify authentication operations
- **Hooks**: React hooks for authentication state
- **Utils**: Validation and helper functions

## Structure

```
src/
├── services/
│   └── authService.js      # AWS Amplify auth operations
├── hooks/
│   └── useAuth.js          # Authentication state hook
└── utils/
    └── validation.js       # Input validation functions
```

## Usage

### Auth Service

```javascript
import {
  signUpUser,
  confirmUserSignUp,
  signInUser,
  signOutUser,
  getCurrentAuthUser
} from '@pantry-app/shared/services/authService';

// Sign up a new user
await signUpUser('user@example.com', 'SecurePass123');

// Confirm email with verification code
await confirmUserSignUp('user@example.com', '123456');

// Sign in
const user = await signInUser('user@example.com', 'SecurePass123');

// Get current user
const currentUser = await getCurrentAuthUser();

// Sign out
await signOutUser();
```

### Validation

```javascript
import {
  validateEmail,
  validatePassword,
  validateVerificationCode
} from '@pantry-app/shared/utils/validation';

const emailError = validateEmail('test@example.com');
const passwordError = validatePassword('SecurePass123');
const codeError = validateVerificationCode('123456');
```

## Testing

```bash
npm test
```

## Dependencies

- **aws-amplify**: AWS SDK for authentication (works on web and mobile)

## Design Principles

- **Platform-agnostic**: No web or mobile-specific code
- **Minimal dependencies**: Only AWS Amplify required
- **Pure functions**: Easy to test and reason about
- **Clear interfaces**: Simple, documented APIs
