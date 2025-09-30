import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { themes, Theme, ThemeName } from '../styles/themes';
import * as api from '../services/api';

type ThemeProviderState = {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  themes: Theme[];
  font: string;
  setFont: (font: string) => void;
};

const initialState: ThemeProviderState = {
  theme: 'slate',
  setTheme: () => null,
  themes: themes,
  font: '',
  setFont: () => null,
};

const ThemeProviderContext = createContext<ThemeProviderState>(initialState);

const DEFAULT_FONT = 'Asap';

export function ThemeProvider({ children }: { children?: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>('slate');
  const [font, setFontState] = useState<string>('');

  // Effect to apply theme styles to the DOM whenever the `theme` state changes.
  useEffect(() => {
    const root = window.document.documentElement;
    const selectedTheme = themes.find(t => t.name === theme) ?? themes[0];
    
    root.classList.remove(...themes.map(t => t.name));
    root.classList.add(selectedTheme.name);

    for (const [key, value] of Object.entries(selectedTheme.colors)) {
        root.style.setProperty(key, value);
    }
  }, [theme]);
  
  // Effect to apply font styles to the DOM whenever the `font` state changes.
  useEffect(() => {
    const root = window.document.documentElement;
    const linkId = 'google-font-dynamic-link';
    let linkElement = document.getElementById(linkId) as HTMLLinkElement | null;

    if (font) {
        root.style.setProperty('--font-sans', font);

        if (!linkElement) {
            linkElement = document.createElement('link');
            linkElement.id = linkId;
            linkElement.rel = 'stylesheet';
            document.head.appendChild(linkElement);
        }

        const encodedFont = font.replace(/ /g, '+');
        linkElement.href = `https://fonts.googleapis.com/css2?family=${encodedFont}:wght@400;500;600;700&display=swap`;
    } else {
        root.style.setProperty('--font-sans', DEFAULT_FONT);
        if (linkElement) {
            linkElement.remove();
        }
    }
  }, [font]);

  // This effect runs once on mount to initialize theme and font from the backend.
  useEffect(() => {
    const initializeAppearance = async () => {
      // 1. Fetch the initial source of truth from the backend.
      try {
        const appearance = await api.getAppearance();
        
        if (appearance?.theme && themes.some(t => t.name === appearance.theme)) {
          setThemeState(appearance.theme as ThemeName);
        }
        
        if (appearance?.hasOwnProperty('font')) {
          setFontState(appearance.font ?? '');
        }
      } catch (e) {
        console.error("Failed to fetch appearance settings, using defaults:", e);
      }

      // 2. Only after initialization, set up the API for the backend to push live updates.
      // This prevents a race condition where a backend push overwrites the initial fetch.
      window.frontendApi = {
        setTheme: (themeName: ThemeName) => {
          if (themes.some(t => t.name === themeName)) {
            setThemeState(themeName);
          }
        },
        setFont: (fontName: string) => {
          setFontState(fontName);
        },
      };
    };

    initializeAppearance();
  }, []);

  // Function for the UI to call to change the theme and persist it.
  const setTheme = useCallback((newTheme: ThemeName) => {
    if (!themes.some(t => t.name === newTheme)) {
      console.warn(`Attempted to set an invalid theme: "${newTheme}"`);
      return;
    }
    setThemeState(newTheme); // Optimistic update
    api.updateAppearance({ theme: newTheme }).catch(e => {
      console.error("Failed to save theme to backend:", e);
    });
  }, []);

  // Function for the UI to call to change the font and persist it.
  const setFont = useCallback((newFont: string) => {
    const trimmedFont = newFont.trim();
    setFontState(trimmedFont); // Optimistic update
    api.updateAppearance({ font: trimmedFont }).catch(e => {
      console.error("Failed to save font to backend:", e);
    });
  }, []);

  const value = {
    theme,
    setTheme,
    themes,
    font,
    setFont,
  };

  return (
    <ThemeProviderContext.Provider value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
