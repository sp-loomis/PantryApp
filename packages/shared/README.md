# Pantry App - Shared Package

Platform-agnostic business logic for authentication.

## Purpose

This package contains shared code that can be used by both web (React) and mobile (React Native) applications.

## Contents

### Services
- `authService.js` - AWS Amplify authentication operations

### Hooks
- `useAuth.js` - Authentication state management hook

### Utilities
- `validation.js` - Form validation helpers

## Usage

Import from the shared package:

```javascript
import { useAuth, validateEmail, signInUser } from '@pantry-app/shared';
```

## Platform Compatibility

All code in this package is platform-agnostic and works with:
- React (web)
- React Native (mobile)

## Dependencies

- `aws-amplify` - AWS authentication SDK (works on both web and mobile)
- `react` - For hooks (peer dependency)

## Testing

Run tests:
```bash
npm run test
```
