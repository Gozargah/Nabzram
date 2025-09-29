import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { themes, Theme, ThemeName } from '../styles/themes';

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

// FIX: Made the children prop optional to work around a potential JSX parsing issue.
export function ThemeProvider({ children }: { children?: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(() => {
    try {
      const storedTheme = window.localStorage.getItem('app-theme') as ThemeName;
      return themes.some(t => t.name === storedTheme) ? storedTheme : 'slate';
    } catch (e) {
      return 'slate';
    }
  });

  const [font, setFontState] = useState<string>(() => {
    try {
        return window.localStorage.getItem('app-font') ?? '';
    } catch (e) {
        return '';
    }
  });


  useEffect(() => {
    const root = window.document.documentElement;
    const selectedTheme = themes.find(t => t.name === theme) ?? themes[0];
    
    root.classList.remove(...themes.map(t => t.name));
    root.classList.add(selectedTheme.name);

    for (const [key, value] of Object.entries(selectedTheme.colors)) {
        root.style.setProperty(key, value);
    }
  }, [theme]);
  
  useEffect(() => {
    const root = window.document.documentElement;
    const linkId = 'google-font-dynamic-link';
    let linkElement = document.getElementById(linkId) as HTMLLinkElement | null;

    if (font) { // A custom font is set from Google Fonts
        root.style.setProperty('--font-sans', font);

        if (!linkElement) {
            linkElement = document.createElement('link');
            linkElement.id = linkId;
            linkElement.rel = 'stylesheet';
            document.head.appendChild(linkElement);
        }

        const encodedFont = font.replace(/ /g, '+');
        linkElement.href = `https://fonts.googleapis.com/css2?family=${encodedFont}:wght@400;500;600;700&display=swap`;
    } else { // Use the default, local font
        root.style.setProperty('--font-sans', DEFAULT_FONT);
        if (linkElement) {
            linkElement.remove();
        }
    }
  }, [font]);

  const setTheme = useCallback((newTheme: ThemeName) => {
    try {
        window.localStorage.setItem('app-theme', newTheme);
    } catch (e) {
        console.error("Failed to save theme to localStorage", e);
    }
    setThemeState(newTheme);
  }, []);

  const setFont = useCallback((newFont: string) => {
    try {
        window.localStorage.setItem('app-font', newFont);
    } catch(e) {
        console.error("Failed to save font to localStorage", e);
    }
    setFontState(newFont);
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