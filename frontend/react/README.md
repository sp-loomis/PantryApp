# Pantry App - React Frontend

React-based authentication frontend for Pantry App with cross-platform architecture.

## Overview

This directory contains the React frontend implementation with a monorepo structure designed for code sharing between web and future mobile applications.

## Structure

```
frontend/react/
├── shared/          # Platform-agnostic business logic
│   ├── src/
│   │   ├── services/    # AWS Amplify auth operations
│   │   ├── hooks/       # React authentication hooks
│   │   └── utils/       # Validation and helpers
│   └── package.json
│
└── web/             # React web application
    ├── src/
    │   ├── pages/       # Page components
    │   ├── components/  # Reusable UI components
    │   ├── contexts/    # React contexts
    │   ├── config/      # Configuration files
    │   └── theme/       # Chakra UI theme
    └── package.json
```

## Packages

### `shared/` - Platform-Agnostic Logic

Business logic that works across web and mobile:

- **Services**: AWS Amplify authentication operations
- **Hooks**: Custom React hooks for auth state
- **Utils**: Validation functions

Can be imported by both web and mobile apps:

```javascript
import { useAuth, validateEmail } from '@pantry-app/shared';
```

[View shared package documentation](./shared/README.md)

### `web/` - React Web Application

Web UI built with:

- React 18 + Vite
- Chakra UI (components)
- React Router (routing)
- React Hook Form (forms)

[View web package documentation](./web/README.md)

## Quick Start

### Prerequisites

- Node.js 18+
- npm or yarn
- AWS Cognito User Pool configured

### Installation

From project root:

```bash
# Install all dependencies
npm install

# Start web dev server
npm run dev
```

The web app will be available at `http://localhost:5173`

### Configuration

1. Copy environment template:
   ```bash
   cd frontend/react/web
   cp .env.example .env
   ```

2. Add your AWS Cognito credentials to `.env`:
   ```env
   VITE_COGNITO_USER_POOL_ID=us-east-2_xxxxxxxxx
   VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
   VITE_AWS_REGION=us-east-2
   ```

## Features

### Implemented (v1.0)

- ✅ User signup with email verification
- ✅ User login/logout
- ✅ Protected routes
- ✅ Token management and auto-refresh
- ✅ Responsive web interface
- ✅ Shared business logic

### Planned (Future)

- Password reset
- Multi-factor authentication (MFA)
- React Native mobile app
- User profile management
- Inventory management UI

## Architecture

### Design Principles

1. **Separation of Concerns**: UI, business logic, and data layers are distinct
2. **Code Sharing**: Business logic reusable across web and mobile
3. **Platform Agnostic**: Shared package has no web/mobile-specific code
4. **Security First**: Secure token handling, validation, and auth flows

### Code Sharing Strategy

**Shared (~60-70% of code):**
- Authentication service (Amplify)
- Business logic and validation
- Custom hooks
- Constants and configuration

**Platform-Specific:**
- UI components (Chakra UI vs NativeBase)
- Navigation (React Router vs React Navigation)
- Platform APIs

### Mobile Readiness

The architecture supports future React Native app:

1. Create `mobile/` package alongside `web/`
2. Import shared business logic from `shared/`
3. Rebuild UI with native components (NativeBase, React Native Paper)
4. Use React Navigation instead of React Router

The `shared/` package is designed to work identically on mobile.

## Development

### Available Scripts

From project root:

```bash
npm run dev              # Start web dev server
npm run build            # Build web for production
npm run lint             # Lint all packages
npm test                 # Run tests
```

### Testing

Tests can be added using:

- **Vitest** - Unit and integration tests
- **React Testing Library** - Component tests
- **Playwright** - E2E tests (optional)

Test structure:

```
shared/tests/
├── unit/
│   ├── services/authService.test.js
│   └── utils/validation.test.js
└── fixtures/

web/tests/
├── unit/components/
└── integration/flows/
```

## Deployment

### Web Application

**Target**: AWS S3 + CloudFront

```bash
# Build
npm run build

# Deploy to S3
aws s3 sync frontend/react/web/dist/ s3://pantry-app-frontend --delete

# Invalidate CloudFront
aws cloudfront create-invalidation \
  --distribution-id EXXXXX \
  --paths "/*"
```

See [web/README.md](./web/README.md) for detailed deployment instructions.

## Documentation

- [Shared Package README](./shared/README.md) - Business logic documentation
- [Web Package README](./web/README.md) - Web app documentation
- [Design Document](../../AUTHENTICATION.md) - Original design specifications

## Technology Stack

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| Framework | React | 18+ | UI framework |
| Build Tool | Vite | 5+ | Dev server and bundler |
| UI Library | Chakra UI | 2+ | Component library |
| Routing | React Router | 6+ | Client-side routing |
| Backend SDK | AWS Amplify | 6+ | Cognito integration |
| Forms | React Hook Form | 7+ | Form management |
| State | React Context | Built-in | Global state |
| Testing | Vitest | 1+ | Test runner |

## Contributing

### Code Style

- ES2022+ features
- Functional components only
- Arrow functions for consistency
- Destructuring in function signatures

### File Naming

```
Components:    PascalCase.jsx
Hooks:         camelCase.js
Services:      camelCase.js
Tests:         *.test.{js,jsx}
```

### Git Workflow

```bash
# Branch naming
feature/auth-improvements
bugfix/login-validation
refactor/auth-service

# Commit messages
feat: add password reset
fix: handle expired tokens
refactor: extract validation logic
test: add login flow tests
```

## License

MIT
