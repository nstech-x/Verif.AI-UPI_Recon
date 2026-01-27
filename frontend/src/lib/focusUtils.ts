/**
 * Utility functions to handle focus management and prevent cursor blinking issues
 */

// Prevent default focus behavior on non-interactive elements
export const preventFocus = (event: React.FocusEvent) => {
  const target = event.target as HTMLElement;
  
  // Allow focus on interactive elements
  const interactiveElements = [
    'INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'
  ];
  
  const isInteractive = interactiveElements.includes(target.tagName) ||
                       target.hasAttribute('contenteditable') ||
                       target.hasAttribute('tabindex') ||
                       target.getAttribute('role') === 'button';
  
  if (!isInteractive) {
    target.blur();
  }
};

// Remove focus from all elements except inputs
export const clearAllFocus = () => {
  const activeElement = document.activeElement as HTMLElement;
  if (activeElement && activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
    activeElement.blur();
  }
};

// Add event listeners to prevent unwanted focus
export const initializeFocusManagement = () => {
  // Clear focus when clicking on non-interactive elements
  document.addEventListener('click', (event) => {
    const target = event.target as HTMLElement;
    
    // Skip if clicking on interactive elements
    const interactiveElements = ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'];
    const isInteractive = interactiveElements.includes(target.tagName) ||
                         target.hasAttribute('contenteditable') ||
                         target.hasAttribute('tabindex') ||
                         target.getAttribute('role') === 'button' ||
                         target.closest('button') ||
                         target.closest('a') ||
                         target.closest('[role="button"]');
    
    if (!isInteractive) {
      // Clear any existing focus
      setTimeout(() => {
        const activeElement = document.activeElement as HTMLElement;
        if (activeElement && activeElement !== document.body) {
          activeElement.blur();
        }
      }, 0);
    }
  });

  // Prevent tab focus on non-interactive elements
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Tab') {
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement && !isInteractiveElement(activeElement)) {
        event.preventDefault();
        focusNextInteractiveElement();
      }
    }
  });
};

// Check if element is interactive
const isInteractiveElement = (element: HTMLElement): boolean => {
  const interactiveElements = ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'];
  return interactiveElements.includes(element.tagName) ||
         element.hasAttribute('contenteditable') ||
         element.hasAttribute('tabindex') ||
         element.getAttribute('role') === 'button';
};

// Focus next interactive element
const focusNextInteractiveElement = () => {
  const interactiveElements = document.querySelectorAll(
    'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
  );
  
  if (interactiveElements.length > 0) {
    (interactiveElements[0] as HTMLElement).focus();
  }
};

// Cleanup function
export const cleanupFocusManagement = () => {
  // Remove event listeners if needed
  // This would be called in component cleanup
};