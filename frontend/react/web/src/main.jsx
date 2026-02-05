/**
 * Application Entry Point
 *
 * Initializes Amplify and renders the React app.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { configureAmplify } from './config/amplify';

// Configure AWS Amplify
configureAmplify();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
