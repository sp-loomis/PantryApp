# Pantry App - Web Frontend

React-based authentication frontend for Pantry App.

## Features

- User signup with email verification
- User login/logout
- Protected route handling
- Token management and auto-refresh
- Responsive web interface

## Tech Stack

- React 18+
- Vite (build tool)
- Chakra UI (component library)
- React Router (routing)
- AWS Amplify (authentication)
- React Hook Form (form management)

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

3. Update `.env` with your AWS Cognito credentials:
   - `VITE_COGNITO_USER_POOL_ID`
   - `VITE_COGNITO_CLIENT_ID`
   - `VITE_AWS_REGION`

## Development

Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:5173`

## Build

Build for production:
```bash
npm run build
```

Output will be in the `dist/` directory.

## Testing

Run tests:
```bash
npm run test
```

## Project Structure

```
src/
├── main.jsx              # Entry point
├── App.jsx               # Main app component
├── config/
│   └── amplify.js        # Amplify configuration
├── theme/
│   └── theme.js          # Chakra UI theme
├── contexts/
│   └── AuthContext.jsx   # Authentication context
├── pages/
│   ├── LoginPage.jsx     # Login page
│   ├── SignupPage.jsx    # Signup page
│   ├── ConfirmPage.jsx   # Email confirmation page
│   └── HomePage.jsx      # Home page (protected)
└── components/
    ├── ProtectedRoute.jsx
    ├── AuthLayout.jsx
    └── ErrorMessage.jsx
```

## Environment Variables

Required:
- `VITE_COGNITO_USER_POOL_ID` - AWS Cognito User Pool ID
- `VITE_COGNITO_CLIENT_ID` - AWS Cognito App Client ID
- `VITE_AWS_REGION` - AWS Region (default: us-east-2)

Optional:
- `VITE_APP_NAME` - Application name
- `VITE_APP_URL` - Application URL
