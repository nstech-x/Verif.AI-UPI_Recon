import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './App.css'
import App from './App.tsx'
import { initializeFocusManagement } from './lib/focusUtils'

// Initialize focus management when the app starts
const AppWithFocusManagement = () => {
  useEffect(() => {
    initializeFocusManagement();
  }, []);
  
  return <App />;
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppWithFocusManagement />
  </StrictMode>,
)
