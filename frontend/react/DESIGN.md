# React Authentication Frontend - Design Document

**Version:** 1.0
**Date:** 2026-02-04
**Status:** Approved

## Overview

### Purpose

Define the architecture for a React-based authentication frontend for Pantry App, supporting user signup, email confirmation, login, and logout with a focus on functionality over visual polish.

### Design Goals

1. **Functional First**: Prioritize working authentication over polished UI/UX
2. **Cross-Platform Ready**: Build for web with architecture supporting future native mobile app
3. **Security**: Implement secure token handling and authentication flows
4. **Maintainability**: Use established patterns and well-supported libraries
5. **Extensibility**: Design to support future inventory management features

### Scope

**In Scope:**
- User signup with email verification
- User login/logout
- Protected route handling
- Token management and auto-refresh
- Responsive web interface
- Shared business logic for future mobile

**Out of Scope:**
- Password reset
- Social authentication
- MFA
- User profile management
- Inventory management UI

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Application                     │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  UI Components │──│ Auth Context │──│   Routes    │ │
│  │  (Chakra UI)   │  │   (State)    │  │ (React      │ │
│  └────────────────┘  └──────────────┘  │  Router)    │ │
│           │                  │          └─────────────┘ │
│  ┌────────┴──────────────────┴──────────────────────┐  │
│  │         Business Logic (Shared Layer)            │  │
│  │      Auth Service │ Hooks │ Utils                │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                       │ AWS Amplify
                       ▼
┌─────────────────────────────────────────────────────────┐
│   AWS Cognito User Pool  →  Lambda + API Gateway       │
└─────────────────────────────────────────────────────────┘
```

### Architecture Principles

1. **Separation of Concerns**: UI, business logic, and data layers are distinct
2. **Shared Logic**: Business logic designed for reuse across web and mobile
3. **Unidirectional Data Flow**: State flows down, events flow up
4. **Service Layer**: AWS interactions isolated in service modules

---

## Technology Stack

| Category | Technology | Version | Rationale |
|----------|-----------|---------|-----------|
| **Framework** | React | 18+ | Industry standard, mobile support via React Native |
| **Build Tool** | Vite | 5+ | Fast dev server, modern tooling |
| **UI Library** | Chakra UI | 2+ | Complete component system, accessibility built-in |
| **Routing** | React Router | 6+ | Standard client-side routing |
| **Backend** | AWS Amplify | 6+ | Official AWS SDK, modular, works web + mobile |
| **Forms** | React Hook Form | 7+ | Performant, good validation support |
| **State** | React Context | Built-in | Sufficient for auth state |
| **Testing** | Vitest | 1+ | Native Vite integration, fast |
| **Testing** | React Testing Library | 14+ | User-centric testing, industry standard |
| **E2E** | Playwright | 1+ | Multi-browser support (optional for MVP) |

---

## Project Structure

### Monorepo Organization

```
pantry-app/
├── packages/
│   ├── shared/                          # Platform-agnostic business logic
│   │   ├── src/
│   │   │   ├── services/
│   │   │   │   └── authService.js       # Amplify auth operations
│   │   │   ├── hooks/
│   │   │   │   └── useAuth.js           # Auth state hook
│   │   │   └── utils/
│   │   │       └── validation.js        # Form validation
│   │   └── tests/
│   │
│   ├── web/                             # React web application
│   │   ├── src/
│   │   │   ├── main.jsx
│   │   │   ├── App.jsx
│   │   │   ├── config/
│   │   │   │   └── amplify.js           # Amplify config
│   │   │   ├── theme/
│   │   │   │   └── theme.js             # Chakra theme
│   │   │   ├── contexts/
│   │   │   │   └── AuthContext.jsx      # Auth provider
│   │   │   ├── pages/
│   │   │   │   ├── LoginPage.jsx
│   │   │   │   ├── SignupPage.jsx
│   │   │   │   ├── ConfirmPage.jsx
│   │   │   │   └── HomePage.jsx
│   │   │   └── components/
│   │   │       ├── ProtectedRoute.jsx
│   │   │       ├── AuthLayout.jsx
│   │   │       └── ErrorMessage.jsx
│   │   └── tests/
│   │
│   └── mobile/                          # React Native (future)
│
└── package.json                         # Workspace config
```

**Module Responsibilities:**

- **Shared**: Auth service, hooks, validation - reusable across platforms
- **Web**: UI components, routing, web-specific implementation
- **Mobile (Future)**: Native UI, navigation, mobile-specific implementation

---

## Authentication Architecture

### Core Flows

**Signup Flow:** User input → Validation → Amplify signUp → Email verification → Redirect to confirm

**Confirmation Flow:** Verification code → Amplify confirmSignUp → Redirect to login

**Login Flow:** Credentials → Amplify signIn → Tokens stored → Update context → Redirect to home

**Token Refresh:** Auto-handled by Amplify before expiry

**Logout Flow:** signOut → Clear tokens → Update context → Redirect to login

### Auth Service Interface

```javascript
// packages/shared/src/services/authService.js

export async function signUpUser(email, password)
export async function confirmUserSignUp(email, code)
export async function signInUser(email, password)
export async function signOutUser()
export async function getCurrentAuthUser()
```

### AuthContext State Shape

```javascript
{
  user: { email, userId, emailVerified } | null,
  isAuthenticated: boolean,
  isLoading: boolean,
  error: string | null,

  // Methods
  login: (email, password) => Promise<void>,
  signup: (email, password) => Promise<void>,
  confirmSignup: (email, code) => Promise<void>,
  logout: () => Promise<void>,
  clearError: () => void
}
```

---

## Component Design

### Page Components

**LoginPage**
- Login form (email, password)
- Validation via React Hook Form
- Error display
- Link to signup

**SignupPage**
- Signup form (email, password, confirm password)
- Password strength validation
- Error handling
- Link to login

**ConfirmPage**
- Email confirmation form (email, code)
- Accepts email from navigation state
- Error handling

**HomePage**
- Welcome message with user email
- Logout button
- Protected by ProtectedRoute

### Shared Components

**ProtectedRoute**
- Check authentication from context
- Redirect to login if not authenticated
- Show loading state while checking

**AuthLayout**
- Consistent layout for auth pages
- Centered card on desktop, full-width on mobile

**ErrorMessage**
- Consistent error display
- Maps Cognito errors to user-friendly messages

---

## Mobile Strategy

### Code Sharing

**Shared (~60-70% of code):**
- Auth service (Amplify works both platforms)
- Business logic and validation
- Custom hooks
- Constants and configuration

**Platform-Specific:**
- UI components (Chakra UI vs NativeBase)
- Navigation (React Router vs React Navigation)
- Storage (handled by Amplify automatically)

**Migration Path:**
1. Build web with shared logic properly separated
2. Create mobile package
3. Import shared business logic
4. Rebuild UI with native components

---

## Testing Standards

### Test Organization

```
packages/shared/tests/
├── unit/
│   ├── services/authService.test.js
│   ├── hooks/useAuth.test.js
│   └── utils/validation.test.js
└── fixtures/authData.js

packages/web/tests/
├── unit/components/
├── integration/
│   ├── pages/
│   └── flows/authFlow.test.jsx
└── e2e/auth.spec.js
```

### Testing Philosophy

**Test Priorities (High to Low):**
1. Auth business logic (critical - 85%+ coverage)
2. User flows (signup, login, logout)
3. Error handling (auth failures, network errors)
4. UI behavior (form validation, navigation)
5. Visual appearance (low priority - manual QA)

### Test Coverage Targets

- Shared business logic: **85%+**
- Auth services: **90%+**
- UI components: **60%+**
- Integration flows: **Critical paths covered**

### What NOT to Test

- Chakra UI internals
- React Hook Form internals
- Amplify SDK
- Simple presentational components
- Exact UI styling

### Vitest Configuration

```javascript
// vitest.config.js
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.js',
    coverage: {
      provider: 'c8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['**/*.test.{js,jsx}', '**/main.jsx']
    }
  }
})
```

### Mock Strategy

- Mock AWS Amplify auth functions globally in test setup
- Use fixtures for consistent test data
- Integration tests mock at service boundary
- E2E tests use real Cognito (test user pool)

---

## Security

### Key Requirements

**Token Management:**
- Amplify handles token storage (web: encrypted localStorage, mobile: Keychain/Keystore)
- Automatic token refresh before expiry
- Tokens cleared on logout and auth errors
- No manual token manipulation

**Password Handling:**
- Never logged or stored
- Transmitted only over HTTPS
- Enforced by Cognito password policy
- Input type="password" prevents visibility

**Input Validation:**
- Client-side validation for UX (React Hook Form)
- Server-side validation by Cognito (security)
- Email format and password strength enforced
- XSS prevention via React's JSX escaping

**Error Messages:**
- Generic messages don't reveal user existence
- No stack traces exposed to users
- Same message for "user not found" and "wrong password"

**HTTPS:**
- All production traffic over HTTPS
- HTTP redirects to HTTPS
- CSP headers configured

**Dependencies:**
- Regular `npm audit` checks
- Automated dependency updates
- Pin major versions

---

## Configuration

### Environment Variables

```bash
# AWS Cognito
VITE_COGNITO_USER_POOL_ID=us-east-2_xxxxxxxxx
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_AWS_REGION=us-east-2

# Application
VITE_APP_NAME=Pantry App
VITE_APP_URL=https://pantry.example.com

# API (Future)
VITE_API_GATEWAY_URL=https://xxx.execute-api.us-east-2.amazonaws.com/dev
```

### Cognito Requirements

**User Pool Settings:**
- Username: Email
- Email verification: Required
- Password policy: 8+ chars, uppercase, lowercase, numbers

**App Client:**
- Auth flow: USER_PASSWORD_AUTH enabled
- Client secret: None (public web client)
- Token expiry: Access/ID 1hr, Refresh 30 days

### CORS Configuration

```json
{
  "Access-Control-Allow-Origin": "https://pantry.example.com",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization"
}
```

Development: `http://localhost:5173`

---

## Build & Deployment

### Build Process

**Development:**
```bash
npm run dev              # Vite dev server at localhost:5173
```

**Production:**
```bash
npm run build            # Output: packages/web/dist/
```

**Build Output:**
- Minification and tree-shaking via Vite
- Code splitting for routes
- Hashed filenames for cache busting
- Target bundle size: < 200KB gzipped

### Deployment: AWS S3 + CloudFront

**Advantages:**
- Native AWS integration
- CDN distribution globally
- HTTPS by default
- Cost-effective and scalable

**Process:**
```bash
npm run build
aws s3 sync dist/ s3://pantry-app-frontend --delete
aws cloudfront create-invalidation --distribution-id EXXXXX --paths "/*"
```

### CI/CD Pipeline

**GitHub Actions workflow:**
- Run tests on pull requests
- Build on main branch push
- Deploy to S3 if tests pass
- Invalidate CloudFront cache
- Environment secrets from GitHub Secrets

### Performance Targets

- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s
- Bundle size: < 200KB gzipped
- Lighthouse score: > 90

---

## Standards & Best Practices

### Code Style

- ES2022+ features
- Functional components only
- Arrow functions for consistency
- Destructuring in function signatures

### File Naming

```
Components:    PascalCase.jsx      (LoginPage.jsx)
Hooks:         camelCase.js        (useAuth.js)
Services:      camelCase.js        (authService.js)
Tests:         *.test.{js,jsx}     (authService.test.js)
```

### Git Workflow

**Branch naming:**
```
feature/auth-signup
bugfix/login-error
refactor/auth-service
```

**Commit messages:**
```
feat: add signup page
fix: handle token expiry
refactor: extract auth logic
test: add login flow tests
```

### Accessibility

- WCAG 2.1 AA compliance
- Keyboard navigation for all interactions
- ARIA labels on form inputs
- Screen reader compatible
- Color contrast > 4.5:1

---

## Success Criteria

### Functional Requirements

1. **Signup & Confirmation**
   - User can create account with email/password
   - Password validation enforced
   - User receives and enters verification code
   - Clear error messages

2. **Login & Logout**
   - User logs in with confirmed credentials
   - Invalid credentials show clear errors
   - Logout clears session and redirects

3. **Protected Access**
   - Home page accessible only when authenticated
   - Unauthenticated users redirected to login
   - User info displayed on home page

4. **Token Management**
   - Tokens auto-refresh before expiry
   - Session persists across browser refreshes
   - Expired tokens trigger re-authentication

### Non-Functional Requirements

**Performance:**
- Initial load < 2s on 3G
- Form response < 1s
- Bundle < 200KB gzipped
- Lighthouse > 90

**Responsiveness:**
- Works on mobile (320px+), tablet (768px+), desktop (1024px+)
- Touch-friendly on mobile

**Browser Compatibility:**
- Chrome, Firefox, Safari, Edge (latest 2 versions)

**Accessibility:**
- Keyboard navigation works
- Screen reader compatible
- WCAG 2.1 AA compliant

**Security:**
- HTTPS in production
- Tokens stored securely
- No sensitive data in logs
- Input validation enforced
- Generic error messages

**Code Quality:**
- Test coverage > 80% for auth logic
- No console errors
- ESLint passes
- Accessibility audit passes

### Development Requirements

**Architecture:**
- Business logic separated from UI
- Shared package works independently
- Ready for mobile code sharing

**Documentation:**
- README with setup instructions
- Environment variables documented
- Component usage examples

**Testing:**
- Unit tests for services
- Integration tests for flows
- Tests pass in CI/CD

**Deployment:**
- Production builds successfully
- Environment variables configurable
- Deployable to S3 + CloudFront

---

## Appendices

### Related Documents

- Pantry App Backend API Documentation
- AWS Cognito Configuration
- CLI Authentication Guide

### Technology Links

- [React](https://react.dev/)
- [Vite](https://vitejs.dev/)
- [Chakra UI](https://chakra-ui.com/)
- [AWS Amplify](https://docs.amplify.aws/)
- [React Router](https://reactrouter.com/)
- [React Hook Form](https://react-hook-form.com/)
- [Vitest](https://vitest.dev/)

---

**Document Status:** Draft - Awaiting Review

**Next Steps:**
1. Review design with stakeholders
2. Validate technology choices
3. Confirm security requirements
4. Approve before implementation
