# Pantry App - Web Frontend

React web application for Pantry App with AWS Cognito authentication.

## Features

- User signup with email verification
- User login/logout
- Protected routes
- Token management with auto-refresh
- Responsive design (mobile, tablet, desktop)
- Accessible UI components

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **Chakra UI** - Component library
- **React Router** - Client-side routing
- **React Hook Form** - Form management
- **AWS Amplify** - AWS Cognito integration

## Prerequisites

- Node.js 18+ and npm
- AWS Cognito User Pool configured
- User Pool Client ID (public client, no secret)

## Setup

### 1. Install Dependencies

From the project root:

```bash
npm install
```

This will install dependencies for all packages (shared and web).

### 2. Configure Environment

Create `.env` file in `frontend/react/web/`:

```bash
cd frontend/react/web
cp .env.example .env
```

Edit `.env` and add your AWS Cognito credentials:

```env
VITE_COGNITO_USER_POOL_ID=us-east-2_xxxxxxxxx
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_AWS_REGION=us-east-2
```

### 3. Start Development Server

From the project root:

```bash
npm run dev
```

Or from the web package directory:

```bash
cd frontend/react/web
npm run dev
```

The app will be available at `http://localhost:5173`

## Available Scripts

### Development

```bash
npm run dev          # Start Vite dev server (hot reload)
```

### Production

```bash
npm run build        # Build for production (output: dist/)
npm run preview      # Preview production build locally
```

### Code Quality

```bash
npm run lint         # Run ESLint
npm test             # Run tests with Vitest
```

## Project Structure

```
frontend/react/web/
├── src/
│   ├── main.jsx                 # App entry point
│   ├── App.jsx                  # Root component with routing
│   ├── config/
│   │   └── amplify.js           # AWS Amplify configuration
│   ├── theme/
│   │   └── theme.js             # Chakra UI theme
│   ├── contexts/
│   │   └── AuthContext.jsx      # Authentication context
│   ├── components/
│   │   ├── ProtectedRoute.jsx   # Route protection
│   │   ├── AuthLayout.jsx       # Auth page layout
│   │   └── ErrorMessage.jsx     # Error display
│   └── pages/
│       ├── LoginPage.jsx        # Login form
│       ├── SignupPage.jsx       # Signup form
│       ├── ConfirmPage.jsx      # Email verification
│       └── HomePage.jsx         # Protected home page
├── index.html                   # HTML template
├── vite.config.js               # Vite configuration
├── package.json                 # Dependencies and scripts
└── .env.example                 # Environment template
```

## Authentication Flow

### Signup
1. User enters email and password on `/signup`
2. Password validated (8+ chars, upper, lower, number)
3. AWS Cognito creates user (unconfirmed)
4. Verification code sent to email
5. Redirect to `/confirm`

### Email Confirmation
1. User enters email and 6-digit code on `/confirm`
2. AWS Cognito confirms user account
3. Redirect to `/login` with success message

### Login
1. User enters email and password on `/login`
2. AWS Cognito validates credentials
3. Tokens stored securely by Amplify
4. User info loaded into context
5. Redirect to `/` (home)

### Protected Access
1. `ProtectedRoute` checks authentication status
2. Authenticated: render page
3. Not authenticated: redirect to `/login`

### Logout
1. User clicks "Sign Out" on home page
2. AWS Amplify clears tokens
3. Context updated (user = null)
4. Redirect to `/login`

## Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `VITE_COGNITO_USER_POOL_ID` | AWS Cognito User Pool ID | Yes | `us-east-2_abc123xyz` |
| `VITE_COGNITO_CLIENT_ID` | App Client ID (public) | Yes | `1234567890abcdef` |
| `VITE_AWS_REGION` | AWS Region | Yes | `us-east-2` |
| `VITE_APP_NAME` | Application name | No | `Pantry App` |
| `VITE_APP_URL` | Application URL | No | `http://localhost:5173` |

## Building for Production

### Build

```bash
npm run build
```

Output: `frontend/react/web/dist/`

### Deploy to AWS S3 + CloudFront

```bash
# Build the app
npm run build

# Sync to S3 (replace with your bucket name)
aws s3 sync dist/ s3://pantry-app-frontend --delete

# Invalidate CloudFront cache (replace with your distribution ID)
aws cloudfront create-invalidation \
  --distribution-id EXXXXX \
  --paths "/*"
```

### Environment Variables in Production

Set production environment variables in your deployment environment:
- AWS Amplify Console: Environment variables section
- S3 + CloudFront: Build the app with production `.env` before deploying
- Vercel/Netlify: Add in dashboard settings

## Troubleshooting

### "User pool does not exist"
- Check `VITE_COGNITO_USER_POOL_ID` in `.env`
- Ensure User Pool exists in specified region

### "Client does not exist"
- Check `VITE_COGNITO_CLIENT_ID` in `.env`
- Ensure App Client exists in User Pool

### "User not authenticated" on refresh
- Check browser localStorage (should have Amplify tokens)
- Ensure tokens haven't expired
- Check browser console for errors

### Build errors
- Delete `node_modules` and `package-lock.json`
- Run `npm install` from project root
- Ensure Node.js 18+ is installed

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

Minimum: ES2020 support required

## Security Notes

- Tokens stored in browser localStorage (encrypted by Amplify)
- All API calls over HTTPS in production
- Passwords never logged or stored client-side
- CORS configured on API Gateway
- XSS protection via React JSX escaping

## Next Steps

After setting up authentication, you can:

1. Add inventory management features
2. Integrate with backend API
3. Add testing (Vitest + React Testing Library)
4. Set up CI/CD pipeline
5. Deploy to production

## Related Packages

- `@pantry-app/shared` - Shared authentication logic (services, hooks, utils)

## License

MIT
