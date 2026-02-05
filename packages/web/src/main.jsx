/**
 * Main Entry Point
 * Initialize React application with Amplify
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { configureAmplify } from './config/amplify';

// Configure AWS Amplify
configureAmplify();

// Render React app
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
