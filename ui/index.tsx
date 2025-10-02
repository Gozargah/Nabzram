import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);

const renderApp = () => {
  root.render(
    <React.StrictMode>
      <ThemeProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </ThemeProvider>
    </React.StrictMode>
  );
};

const renderError = (message: string) => {
    // Styling is inline as it's outside the main app's styling context.
    // Using default 'slate' theme colors.
    const errorStyle: React.CSSProperties = {
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        textAlign: 'center',
        height: '100vh',
        fontFamily: 'sans-serif',
        backgroundColor: 'hsl(222.2, 84%, 4.9%)',
        color: 'hsl(210, 40%, 98%)',
        padding: '2rem'
    };
    const h1Style: React.CSSProperties = {
        color: 'hsl(0, 72.2%, 50.6%)', // destructive color from slate theme
        fontSize: '1.5rem',
        marginBottom: '1rem'
    };
    root.render(
        <div style={errorStyle}>
            <h1 style={h1Style}>Application Error</h1>
            <p>{message}</p>
        </div>
    );
};

const MAX_WAIT_TIME = 5000; // 5 seconds
const POLL_INTERVAL = 100; // 100 ms
const startTime = Date.now();

const waitForApi = () => {
  if (window.pywebview && window.pywebview.api) {
    renderApp();
  } else if (Date.now() - startTime > MAX_WAIT_TIME) {
    console.error(`pywebview API not available after ${MAX_WAIT_TIME / 1000} seconds.`);
    renderError('Could not start application. Please restart Nabzram.');
  } else {
    setTimeout(waitForApi, POLL_INTERVAL);
  }
};

// The script is loaded with type="module", which defers execution until the document has been parsed.
// We can start waiting for the API right away.
waitForApi();
