export type ThemeName = 
  | 'slate'
  | 'slate-light'
  | 'terminal-green'
  | 'forest-grove'
  | 'ocean-breeze'
  | 'sunset-peach';

export interface Theme {
  name: ThemeName;
  displayName: string;
  colors: {
    '--background': string;
    '--foreground': string;
    '--card': string;
    '--card-foreground': string;
    '--popover': string;
    '--popover-foreground': string;
    '--primary': string;
    '--primary-foreground': string;
    '--secondary': string;
    '--secondary-foreground': string;
    '--muted': string;
    '--muted-foreground': string;
    '--accent': string;
    '--accent-foreground': string;
    '--destructive': string;
    '--destructive-foreground': string;
    '--border': string;
    '--input': string;
    '--ring': string;
    '--success': string;
  };
}

export const themes: Theme[] = [
  {
    name: 'slate',
    displayName: 'Slate',
    colors: {
        '--background': '222.2 84% 4.9%',
        '--foreground': '210 40% 98%',
        '--card': '222.2 47.4% 11.2%',
        '--card-foreground': '210 40% 98%',
        '--popover': '222.2 84% 4.9%',
        '--popover-foreground': '210 40% 98%',
        '--primary': '202.1 91.1% 52.5%',
        '--primary-foreground': '210 40% 98%',
        '--secondary': '217.2 32.6% 17.5%',
        '--secondary-foreground': '210 40% 98%',
        '--muted': '217.2 32.6% 17.5%',
        '--muted-foreground': '215 20.2% 65.1%',
        '--accent': '217.2 32.6% 22.5%',
        '--accent-foreground': '210 40% 98%',
        '--destructive': '0 72.2% 50.6%',
        '--destructive-foreground': '210 40% 98%',
        '--border': '217.2 32.6% 17.5%',
        '--input': '217.2 32.6% 17.5%',
        '--ring': '202.1 91.1% 52.5%',
        '--success': '142.1 76.2% 36.3%',
    },
  },
  {
    name: 'slate-light',
    displayName: 'Slate Light',
    colors: {
      '--background': '220 14.3% 95.9%',
      '--foreground': '224 71.4% 4.1%',
      '--card': '0 0% 100%',
      '--card-foreground': '224 71.4% 4.1%',
      '--popover': '0 0% 100%',
      '--popover-foreground': '224 71.4% 4.1%',
      '--primary': '217.2 91.2% 59.8%',
      '--primary-foreground': '210 20% 98%',
      '--secondary': '220 14.3% 95.9%',
      '--secondary-foreground': '220.9 39.3% 11%',
      '--muted': '220 14.3% 95.9%',
      '--muted-foreground': '220 8.9% 46.1%',
      '--accent': '220 14.3% 93.9%',
      '--accent-foreground': '220.9 39.3% 11%',
      '--destructive': '0 84.2% 60.2%',
      '--destructive-foreground': '210 20% 98%',
      '--border': '220 13% 91%',
      '--input': '220 13% 91%',
      '--ring': '217.2 91.2% 59.8%',
      '--success': '142.1 76.2% 36.3%',
    },
  },
  {
    name: 'terminal-green',
    displayName: 'Terminal Green',
    colors: {
      '--background': '220 15% 5%',
      '--foreground': '120 100% 75%',
      '--card': '220 15% 10%',
      '--card-foreground': '120 100% 75%',
      '--popover': '220 15% 5%',
      '--popover-foreground': '120 100% 75%',
      '--primary': '120 100% 65%',
      '--primary-foreground': '120 100% 10%',
      '--secondary': '220 15% 15%',
      '--secondary-foreground': '120 100% 75%',
      '--muted': '220 15% 15%',
      '--muted-foreground': '120 50% 50%',
      '--accent': '120 70% 30%',
      '--accent-foreground': '120 100% 75%',
      '--destructive': '30 90% 60%',
      '--destructive-foreground': '30 90% 10%',
      '--border': '220 15% 15%',
      '--input': '220 15% 15%',
      '--ring': '120 100% 65%',
      '--success': '120 100% 65%',
    },
  },
    {
    name: 'forest-grove',
    displayName: 'Forest Grove',
    colors: {
      '--background': '210 30% 12%',
      '--foreground': '100 15% 90%',
      '--card': '210 30% 18%',
      '--card-foreground': '100 15% 90%',
      '--popover': '210 30% 12%',
      '--popover-foreground': '100 15% 90%',
      '--primary': '140 60% 55%',
      '--primary-foreground': '140 60% 10%',
      '--secondary': '210 30% 25%',
      '--secondary-foreground': '100 15% 90%',
      '--muted': '210 30% 25%',
      '--muted-foreground': '210 15% 65%',
      '--accent': '140 60% 45%',
      '--accent-foreground': '100 15% 90%',
      '--destructive': '0 70% 60%',
      '--destructive-foreground': '0 70% 10%',
      '--border': '210 30% 25%',
      '--input': '210 30% 25%',
      '--ring': '140 60% 55%',
      '--success': '140 60% 55%',
    },
  },
  {
    name: 'ocean-breeze',
    displayName: 'Ocean Breeze',
    colors: {
      '--background': '205 90% 96%',
      '--foreground': '215 40% 15%',
      '--card': '0 0% 100%',
      '--card-foreground': '215 40% 15%',
      '--popover': '0 0% 100%',
      '--popover-foreground': '215 40% 15%',
      '--primary': '195 85% 45%',
      '--primary-foreground': '0 0% 100%',
      '--secondary': '205 90% 92%',
      '--secondary-foreground': '215 40% 25%',
      '--muted': '205 90% 92%',
      '--muted-foreground': '215 20% 55%',
      '--accent': '205 90% 88%',
      '--accent-foreground': '215 40% 25%',
      '--destructive': '0 80% 65%',
      '--destructive-foreground': '0 0% 100%',
      '--border': '205 80% 88%',
      '--input': '205 80% 88%',
      '--ring': '195 85% 45%',
      '--success': '160 70% 40%',
    },
  },
  {
    name: 'sunset-peach',
    displayName: 'Sunset Peach',
    colors: {
      '--background': '30 80% 94%',
      '--foreground': '20 30% 20%',
      '--card': '30 100% 98%',
      '--card-foreground': '20 30% 20%',
      '--popover': '30 100% 98%',
      '--popover-foreground': '20 30% 20%',
      '--primary': '24.6 95% 53.1%',
      '--primary-foreground': '60 9.1% 97.8%',
      '--secondary': '30 80% 92%',
      '--secondary-foreground': '20 30% 20%',
      '--muted': '30 80% 92%',
      '--muted-foreground': '20 25% 40%',
      '--accent': '30 80% 90%',
      '--accent-foreground': '20 30% 20%',
      '--destructive': '0 72.2% 50.6%',
      '--destructive-foreground': '60 9.1% 97.8%',
      '--border': '30 80% 88%',
      '--input': '30 80% 88%',
      '--ring': '24.6 95% 53.1%',
      '--success': '110 50% 45%',
    },
  },
];