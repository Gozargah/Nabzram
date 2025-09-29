import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../services/api';
import { XrayVersionInfo } from '../types';
import { useToast } from '../contexts/ToastContext';
import { ArrowDownCircleIcon } from './icons';
import CustomSelect, { SelectOption } from './CustomSelect';
import { formatBytes } from './utils';

interface InstallationRequiredProps {
    onInstallSuccess: () => void;
}

const InstallationRequired: React.FC<InstallationRequiredProps> = ({ onInstallSuccess }) => {
    const [info, setInfo] = useState<XrayVersionInfo | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isInstalling, setIsInstalling] = useState(false);
    const [selectedVersion, setSelectedVersion] = useState('latest');
    const [customVersion, setCustomVersion] = useState('');
    const [selectedAssetSize, setSelectedAssetSize] = useState<number | null>(null);
    const { addToast } = useToast();

    const fetchVersionInfo = useCallback(async () => {
        setIsLoading(true);
        try {
            const versionInfo = await api.getXrayVersionInfo();
            setInfo(versionInfo);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to load version info';
            addToast(message, 'error');
        } finally {
            setIsLoading(false);
        }
    }, [addToast]);

    useEffect(() => {
        fetchVersionInfo();
    }, [fetchVersionInfo]);
    
    useEffect(() => {
        if (!info) return;

        let size: number | null = null;
        if (selectedVersion === 'latest') {
            const latestAsset = info.available_versions.find(a => a.version === info.latest_version);
            if (latestAsset) {
                size = latestAsset.size_bytes;
            }
        } else if (selectedVersion !== 'custom') {
            const selectedAsset = info.available_versions.find(a => a.version === selectedVersion);
            if (selectedAsset) {
                size = selectedAsset.size_bytes;
            }
        }
        setSelectedAssetSize(size);
    }, [selectedVersion, info]);

    const handleInstall = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsInstalling(true);
        const versionToInstall = customVersion.trim() || (selectedVersion === 'latest' ? null : selectedVersion);
        
        addToast(`Installing Xray ${versionToInstall || 'latest'}. This may take a moment...`, 'info');
        
        try {
            await api.updateXray({ version: versionToInstall });
            onInstallSuccess();
        } catch(err) {
            const message = err instanceof Error ? err.message : `Failed to install Xray`;
            addToast(message, 'error');
        } finally {
            setIsInstalling(false);
        }
    };

    const handleVersionSelect = (value: string) => {
        setSelectedVersion(value);
        if (value !== 'custom') {
            setCustomVersion('');
        }
    };

    const handleCustomInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setCustomVersion(e.target.value);
        setSelectedVersion('custom');
    };

    const renderInstallForm = () => {
        if (isLoading) {
            return (
                <div className="flex justify-center items-center h-48">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
                </div>
            );
        }

        if (!info) {
            return <p className="text-center text-destructive">Could not load version information.</p>;
        }

        const versionOptions: SelectOption[] = [
            { value: 'latest', label: `Latest (${info.latest_version})` },
            ...info.available_versions.map(asset => ({ value: asset.version, label: `${asset.version}${asset.size_bytes != null ? ` (${formatBytes(asset.size_bytes)})` : ''}` })),
            { value: 'custom', label: 'Custom...' }
        ];
        
        const buttonText = `Install Xray${selectedAssetSize != null ? ` (${formatBytes(selectedAssetSize)})` : ''}`;

        return (
             <form onSubmit={handleInstall} className="sm:w-3/5 w-full max-w-xl space-y-4 mt-8 animate-fade-in-up">
                <div>
                    <label htmlFor="version-select" className="block text-sm font-medium text-muted-foreground mb-1">Select Version to Install</label>
                    <CustomSelect
                        value={selectedVersion}
                        onChange={handleVersionSelect}
                        disabled={isInstalling}
                        options={versionOptions}
                    />
                </div>
                
                {selectedVersion === 'custom' && (
                    <div>
                        <label htmlFor="custom-version" className="block text-sm font-medium text-muted-foreground mb-1">Custom Version</label>
                        <input
                            type="text"
                            id="custom-version"
                            value={customVersion}
                            onChange={handleCustomInputChange}
                            disabled={isInstalling}
                            className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                            placeholder="e.g., v1.8.0"
                        />
                    </div>
                )}
                
                <div className="pt-2">
                    <button 
                        type="submit" 
                        disabled={isInstalling || (selectedVersion === 'custom' && !customVersion.trim())}
                        className="w-full bg-primary text-primary-foreground font-bold py-3 px-6 rounded-lg hover:bg-primary/90 disabled:bg-primary/50 disabled:cursor-not-allowed transition-all transform hover:scale-105 shadow-lg shadow-primary/30 flex items-center justify-center space-x-2"
                    >
                        {isInstalling ? (
                            <>
                                <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-primary-foreground"></div>
                                <span>Installing...</span>
                            </>
                        ) : (
                            <>
                                <ArrowDownCircleIcon className="h-5 w-5" />
                                <span>{buttonText}</span>
                            </>
                        )}
                    </button>
                </div>
            </form>
        );
    }

    return (
        <div className="flex-1 flex flex-col justify-center items-center text-center p-4 animate-fade-in-up">
            <div className="inline-block p-5 bg-destructive/10 rounded-full mb-6">
                <ArrowDownCircleIcon className="h-16 w-16 text-destructive" />
            </div>
            <h2 className="text-2xl font-bold text-foreground mb-3">Xray Installation Required</h2>
            <p className="text-muted-foreground max-w-md mx-auto">
                Nabzram requires the Xray-core engine to manage connections. Please install it to proceed.
            </p>
            {renderInstallForm()}
        </div>
    );
};

export default InstallationRequired;