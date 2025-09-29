import React, { useState, useEffect, useCallback } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { XrayVersionInfo } from '../types';
import { useToast } from '../contexts/ToastContext';
import { ArrowDownCircleIcon, CloudDownloadIcon } from './icons';
import CustomSelect, { SelectOption } from './CustomSelect';
import { formatBytes } from './utils';

interface UpdateModalProps {
    onClose: () => void;
    onUpdateSuccess: () => void;
}

const UpdateModal: React.FC<UpdateModalProps> = ({ onClose, onUpdateSuccess }) => {
    const [info, setInfo] = useState<XrayVersionInfo | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isUpdating, setIsUpdating] = useState(false);
    const [isUpdatingGeodata, setIsUpdatingGeodata] = useState(false);
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

    const handleUpdate = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsUpdating(true);
        const versionToInstall = customVersion.trim() || (selectedVersion === 'latest' ? null : selectedVersion);
        
        addToast(`Updating Xray to ${versionToInstall || 'latest'}. This may take a moment...`, 'info');
        
        try {
            const response = await api.updateXray({ version: versionToInstall });
            addToast(response.message, 'success');
            onUpdateSuccess();
        } catch(err) {
            const message = err instanceof Error ? err.message : `Failed to update Xray`;
            addToast(message, 'error');
        } finally {
            setIsUpdating(false);
        }
    };

    const handleUpdateGeodata = async () => {
        setIsUpdatingGeodata(true);
        addToast('Updating geodata files (geoip.dat, geosite.dat)...', 'info');
        try {
            const response = await api.updateGeodata();
            addToast(response.message, 'success');
        } catch(err) {
            const message = err instanceof Error ? err.message : 'Failed to update geodata files';
            addToast(message, 'error');
        } finally {
            setIsUpdatingGeodata(false);
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

    const renderContent = () => {
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

        const buttonText = `Update Binary${selectedAssetSize != null ? ` (${formatBytes(selectedAssetSize)})` : ''}`;
        
        return (
            <div className="space-y-6">
                 <form onSubmit={handleUpdate} className="space-y-6">
                    <div>
                        <h3 className="text-md font-semibold text-foreground mb-3">Xray-core Binary</h3>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Current Version:</span>
                                <span className="font-mono text-foreground">{info.current_version || 'Not Found'}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Latest Version:</span>
                                <span className="font-mono text-success">{info.latest_version}</span>
                            </div>
                        </div>
                    </div>

                    <div>
                        <label htmlFor="version-select" className="block text-sm font-medium text-muted-foreground mb-1">Select Version to Update</label>
                        <CustomSelect
                            value={selectedVersion}
                            onChange={handleVersionSelect}
                            disabled={isUpdating || isUpdatingGeodata}
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
                                disabled={isUpdating || isUpdatingGeodata}
                                className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                                placeholder="e.g., v1.8.0"
                            />
                        </div>
                    )}
                    
                    <div className="flex justify-end pt-2">
                        <button 
                            type="submit" 
                            disabled={isUpdating || isUpdatingGeodata || (selectedVersion === 'custom' && !customVersion.trim())}
                            className="bg-primary text-primary-foreground font-bold py-2 px-4 rounded-md hover:bg-primary/90 disabled:bg-primary/50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
                        >
                            {isUpdating ? (
                                <>
                                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-primary-foreground"></div>
                                    <span>Updating...</span>
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

                <hr className="border-border" />
                <div>
                    <h3 className="text-md font-semibold text-foreground mb-2">Geodata Files</h3>
                    <p className="text-xs text-muted-foreground/80 mb-4">
                        Keep your `geoip.dat` and `geosite.dat` files up-to-date for accurate routing.
                    </p>
                    <div className="flex justify-end">
                        <button 
                            onClick={handleUpdateGeodata}
                            disabled={isUpdating || isUpdatingGeodata}
                            className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 disabled:bg-secondary/50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2"
                        >
                            {isUpdatingGeodata ? (
                                <>
                                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-secondary-foreground"></div>
                                    <span>Updating...</span>
                                </>
                            ) : (
                                <>
                                    <CloudDownloadIcon className="h-5 w-5" />
                                    <span>Update Geodata</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <Modal title="Updates Manager" onClose={onClose}>
            {renderContent()}
        </Modal>
    );
};

export default UpdateModal;