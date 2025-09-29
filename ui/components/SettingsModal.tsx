import React, { useState, useEffect, useCallback } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { SettingsUpdate } from '../types';
import { useTheme } from '../contexts/ThemeContext';
import { useToast } from '../contexts/ToastContext';
import CustomSelect, { SelectOption } from './CustomSelect';

interface SettingsModalProps {
    onClose: () => void;
    onSaveSuccess: () => void;
}

const logLevelOptions: SelectOption[] = [
    { value: '', label: 'Default' },
    { value: 'debug', label: 'Debug' },
    { value: 'info', label: 'Info' },
    { value: 'warning', label: 'Warning' },
    { value: 'error', label: 'Error' },
    { value: 'none', label: 'None' },
];

const TabButton: React.FC<{
    tabName: string;
    currentTab: string;
    setTab: (tabName: string) => void;
    children: React.ReactNode;
}> = ({ tabName, currentTab, setTab, children }) => {
    const isActive = tabName === currentTab;
    return (
        <button
            type="button"
            onClick={() => setTab(tabName)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                isActive
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            aria-selected={isActive}
            role="tab"
        >
            {children}
        </button>
    );
};


const SettingsModal: React.FC<SettingsModalProps> = ({ onClose, onSaveSuccess }) => {
    const { setTheme, themes, theme: currentThemeName, font, setFont } = useTheme();
    const [settings, setSettings] = useState<SettingsUpdate>({
        socks_port: undefined,
        http_port: undefined,
        xray_binary: undefined,
        xray_assets_folder: undefined,
        xray_log_level: undefined,
    });
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [fontInput, setFontInput] = useState(font);
    const [activeTab, setActiveTab] = useState<'general' | 'appearance'>('general');
    const { addToast } = useToast();

    const fetchSettings = useCallback(async () => {
        try {
            const currentSettings = await api.getSettings();
            setSettings({
                socks_port: currentSettings.socks_port ?? undefined,
                http_port: currentSettings.http_port ?? undefined,
                xray_binary: currentSettings.xray_binary ?? undefined,
                xray_assets_folder: currentSettings.xray_assets_folder ?? undefined,
                xray_log_level: currentSettings.xray_log_level ?? undefined,
            });
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to load settings';
            addToast(message, 'error');
        } finally {
            setIsLoading(false);
        }
    }, [addToast]);

    useEffect(() => {
        fetchSettings();
    }, [fetchSettings]);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const dataToSave: SettingsUpdate = {
                socks_port: settings.socks_port ? Number(settings.socks_port) : null,
                http_port: settings.http_port ? Number(settings.http_port) : null,
                xray_binary: settings.xray_binary || null,
                xray_assets_folder: settings.xray_assets_folder || null,
                xray_log_level: settings.xray_log_level || null,
            };
            await api.updateSettings(dataToSave);
            addToast('Settings saved successfully! Refreshing status...', 'success');
            onSaveSuccess();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to save settings';
            addToast(message, 'error');
        } finally {
            setIsSaving(false);
        }
    };
    
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        if (name === 'socks_port' || name === 'http_port') {
            setSettings(prev => ({...prev, [name]: value === '' ? undefined : Number(value) }));
        } else {
            setSettings(prev => ({...prev, [name]: value }));
        }
    };

    const handleApplyFont = () => {
        const trimmedFont = fontInput.trim();
        setFont(trimmedFont);
        if (trimmedFont) {
            addToast(`Font set to ${trimmedFont}`, 'success');
        } else {
            addToast(`Font reset to default`, 'success');
        }
    };


    return (
        <Modal title="Settings" onClose={onClose} bodyClassName="!p-0">
            {isLoading ? (
                <div className="flex justify-center items-center h-48">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
                </div>
            ) : (
                <div>
                    <div className="border-b border-border px-6">
                        <nav className="flex space-x-2" aria-label="Tabs" role="tablist">
                             <TabButton tabName="general" currentTab={activeTab} setTab={() => setActiveTab('general')}>
                                General
                            </TabButton>
                            <TabButton tabName="appearance" currentTab={activeTab} setTab={() => setActiveTab('appearance')}>
                                Appearance
                            </TabButton>
                        </nav>
                    </div>

                    <div className="p-6">
                        {activeTab === 'general' && (
                            <form onSubmit={handleSave} className="space-y-6">
                                <div>
                                    <h3 className="text-md font-semibold text-foreground mb-2">Xray Configuration</h3>
                                    <p className="text-xs text-muted-foreground/80 mb-4">
                                        Provide absolute paths for your xray-core binary and assets. Leave blank to allow auto-detection.
                                    </p>
                                    <div>
                                        <label htmlFor="xray_binary" className="block text-sm font-medium text-muted-foreground mb-1">Xray Binary Path</label>
                                        <input
                                            type="text"
                                            id="xray_binary"
                                            name="xray_binary"
                                            value={settings.xray_binary ?? ''}
                                            onChange={handleChange}
                                            className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                                            placeholder="e.g., /usr/local/bin/xray"
                                        />
                                    </div>
                                    <div className="mt-4">
                                        <label htmlFor="xray_assets_folder" className="block text-sm font-medium text-muted-foreground mb-1">Xray Assets Folder</label>
                                        <input
                                            type="text"
                                            id="xray_assets_folder"
                                            name="xray_assets_folder"
                                            value={settings.xray_assets_folder ?? ''}
                                            onChange={handleChange}
                                            className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                                            placeholder="e.g., /usr/local/share/xray"
                                        />
                                    </div>
                                    <div className="mt-4">
                                        <label htmlFor="xray_log_level" className="block text-sm font-medium text-muted-foreground mb-1">Xray Log Level</label>
                                        <CustomSelect
                                            value={settings.xray_log_level ?? ''}
                                            onChange={(value) => setSettings(prev => ({ ...prev, xray_log_level: value }))}
                                            options={logLevelOptions}
                                        />
                                    </div>
                                </div>

                                <hr className="border-border"/>
                                
                                <div>
                                    <h3 className="text-md font-semibold text-foreground mb-2">Proxy Ports</h3>
                                    <p className="text-xs text-muted-foreground/80 mb-4">
                                        Override the default SOCKS and HTTP proxy ports. Leave blank to use defaults.
                                    </p>
                                    <div>
                                        <label htmlFor="socks_port" className="block text-sm font-medium text-muted-foreground mb-1">SOCKS Port</label>
                                        <input
                                            type="number"
                                            id="socks_port"
                                            name="socks_port"
                                            value={settings.socks_port ?? ''}
                                            onChange={handleChange}
                                            className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                                            placeholder="e.g., 1080"
                                            min="0"
                                            max="65535"
                                        />
                                    </div>
                                    <div className="mt-4">
                                        <label htmlFor="http_port" className="block text-sm font-medium text-muted-foreground mb-1">HTTP Port</label>
                                        <input
                                            type="number"
                                            id="http_port"
                                            name="http_port"
                                            value={settings.http_port ?? ''}
                                            onChange={handleChange}
                                            className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                                            placeholder="e.g., 8080"
                                            min="0"
                                            max="65535"
                                        />
                                    </div>
                                </div>
                                
                                <div className="flex justify-end pt-2">
                                    <button 
                                        type="submit" 
                                        disabled={isSaving}
                                        className="bg-primary text-primary-foreground font-bold py-2 px-4 rounded-md hover:bg-primary/90 disabled:bg-primary/50 disabled:cursor-not-allowed transition-colors"
                                    >
                                        {isSaving ? 'Saving...' : 'Save Settings'}
                                    </button>
                                </div>
                            </form>
                        )}
                        {activeTab === 'appearance' && (
                             <div className="space-y-6">
                                <div>
                                    <h3 className="text-md font-semibold text-foreground mb-3">Theme</h3>
                                    <p className="text-xs text-muted-foreground/80 mb-4">
                                        Your theme selection is saved automatically.
                                    </p>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                    {themes.map((theme) => {
                                            const isActive = theme.name === currentThemeName;
                                            return (
                                                <button
                                                    key={theme.name}
                                                    type="button"
                                                    onClick={() => setTheme(theme.name)}
                                                    className={`p-2 rounded-lg border-2 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-card ${
                                                        isActive ? 'border-primary' : 'border-transparent hover:border-border'
                                                    }`}
                                                    aria-pressed={isActive}
                                                >
                                                    <div className="w-full h-10 rounded-md flex overflow-hidden mb-2 shadow-inner border border-border/20">
                                                        <div
                                                            className="w-2/3 h-full"
                                                            style={{ backgroundColor: `hsl(${theme.colors['--card']})` }}
                                                        />
                                                        <div
                                                            className="w-1/3 h-full"
                                                            style={{ backgroundColor: `hsl(${theme.colors['--primary']})` }}
                                                        />
                                                    </div>
                                                    <span className={`block text-center text-xs font-medium ${isActive ? 'text-primary' : 'text-foreground'}`}>
                                                        {theme.displayName}
                                                    </span>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>

                                <hr className="border-border"/>

                                <div>
                                    <h3 className="text-md font-semibold text-foreground mb-3">Font</h3>
                                    <p className="text-xs text-muted-foreground/80 mb-4">
                                        Enter a Google Font name. Leave blank to use the default font.
                                    </p>
                                    <div className="flex items-center space-x-2">
                                        <input
                                            type="text"
                                            value={fontInput}
                                            onChange={(e) => setFontInput(e.target.value)}
                                            onKeyDown={(e) => { if (e.key === 'Enter') handleApplyFont(); }}
                                            className="flex-grow bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                                            placeholder="e.g., Roboto (leave blank for default)"
                                        />
                                        <button
                                            type="button"
                                            onClick={handleApplyFont}
                                            className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors"
                                        >
                                            Apply
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </Modal>
    );
};

export default SettingsModal;