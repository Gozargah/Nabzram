import React, { useState, useEffect, useCallback } from 'react';
import { Subscription, ServerStatusResponse, SystemInfo } from './types';
import * as api from './services/api';
import SubscriptionList from './components/SubscriptionList';
import StatusIndicator from './components/StatusIndicator';
import AddSubscriptionModal from './components/AddSubscriptionModal';
import SettingsModal from './components/SettingsModal';
import LogStreamModal from './components/LogStreamModal';
import UpdateModal from './components/UpdateModal';
import { CogIcon, NabzramIcon, MinimizeIcon, XIcon } from './components/icons';
import ToastContainer from './components/ToastContainer';
import { useToast } from './contexts/ToastContext';
import InstallationRequired from './components/InstallationRequired';

declare global {
    interface Window {
        pywebview?: {
            api: {
                minimize: () => void;
                close: () => void;
            }
        }
    }
}

const App: React.FC = () => {
    const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
    const [currentStatus, setCurrentStatus] = useState<ServerStatusResponse | null>(null);
    const [xrayStatus, setXrayStatus] = useState<SystemInfo | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isConnecting, setIsConnecting] = useState(false);
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
    const [isLogsModalOpen, setIsLogsModalOpen] = useState(false);
    const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
    const { addToast } = useToast();

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const [subs, status, xray] = await Promise.all([
                api.getSubscriptions(),
                api.getServerStatus(),
                api.getXrayStatus(),
            ]);
            setSubscriptions(subs);
            setCurrentStatus(status);
            setXrayStatus(xray);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'An unknown error occurred.';
            addToast(`Failed to load data: ${message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    }, [addToast]);

    const fetchStatus = useCallback(async () => {
        try {
            const status = await api.getServerStatus();
            setCurrentStatus(status);
        } catch (err) {
            console.error("Failed to fetch status:", err);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const statusInterval = setInterval(fetchStatus, 5000); // Poll status every 5 seconds
        return () => clearInterval(statusInterval);
    }, [fetchData, fetchStatus]);


    const onAddSubscriptionSuccess = () => {
        addToast('Subscription added successfully!', 'success');
        setIsAddModalOpen(false);
        fetchData();
    };
    
    const onInstallSuccess = () => {
        addToast('Xray installed successfully!', 'success');
        fetchData();
    };

    const onUpdateSuccess = () => {
        setIsUpdateModalOpen(false);
        fetchData();
    };
    
    const onSettingsSaveSuccess = () => {
        setIsSettingsModalOpen(false);
        fetchData();
    };

    const handleStopServer = async () => {
        try {
            await api.stopServer();
            addToast('Server stopped successfully.', 'success');
            fetchStatus();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to stop server.';
            addToast(message, 'error');
        }
    };

    const handleAutoConnect = async () => {
        if (subscriptions.length === 0) {
            addToast('Please add a subscription first.', 'info');
            return;
        }
        setIsConnecting(true);
        addToast('Finding the fastest server...', 'info');
        
        let connected = false;

        for (const sub of subscriptions) {
            addToast(`Testing subscription: ${sub.name}`, 'info');
            try {
                const response = await api.testSubscriptionServers(sub.id);
                const successfulTests = response.results
                    .filter(r => r.success && r.ping_ms !== null && r.ping_ms > 0)
                    .sort((a, b) => a.ping_ms! - b.ping_ms!);

                if (successfulTests.length > 0) {
                    const bestServer = successfulTests[0];
                    await api.startServer(sub.id, bestServer.server_id);
                    addToast(`Connected via ${sub.name} to ${bestServer.remarks} (${bestServer.ping_ms}ms)`, 'success');
                    fetchStatus();
                    connected = true;
                    break;
                }
            } catch (err) {
                const detail = err instanceof Error ? err.message : `Failed to test subscription.`;
                addToast(`Skipping ${sub.name}: ${detail}`, 'error');
            }
        }

        if (!connected) {
            addToast('Auto-connect failed: No responsive servers found in any subscription.', 'error');
        }

        setIsConnecting(false);
    };

    const handleMinimize = () => {
        if (window.pywebview?.api?.minimize) {
            window.pywebview.api.minimize();
        } else {
            console.warn('pywebview API not available to minimize window.');
        }
    };

    const handleClose = () => {
        if (window.pywebview?.api?.close) {
            window.pywebview.api.close();
        } else {
            console.warn('pywebview API not available to close window.');
        }
    };
    
    const renderContent = () => {
        if (isLoading) {
            return (
                <div className="flex-1 flex justify-center items-center">
                    <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-primary"></div>
                </div>
            );
        }

        if (xrayStatus && !xrayStatus.available) {
            return <InstallationRequired onInstallSuccess={onInstallSuccess} />;
        }

        return (
            <div className="flex-1 overflow-y-auto">
                <main>
                    <div className="container mx-auto max-w-lg px-4 pt-6 pb-4">
                        <StatusIndicator 
                            status={currentStatus}
                            xrayStatus={xrayStatus}
                            isConnecting={isConnecting}
                            onConnect={handleAutoConnect}
                            onStop={handleStopServer} 
                            onOpenLogs={() => setIsLogsModalOpen(true)}
                            onOpenUpdates={() => setIsUpdateModalOpen(true)}
                        />
                        
                        <SubscriptionList
                            subscriptions={subscriptions}
                            onAdd={() => setIsAddModalOpen(true)}
                            refreshList={fetchData}
                            currentStatus={currentStatus}
                            onConnect={fetchStatus}
                        />
                    </div>
                </main>
            </div>
        );
    };

    return (
        <div className="bg-background text-foreground h-screen flex flex-col font-sans">
            <ToastContainer />
            
            {/* Fixed, Draggable Title Bar */}
            <div className="pywebview-drag-region h-12 flex-shrink-0 flex justify-between items-center px-4 border-b border-border">
                <div className="flex items-center space-x-3">
                    <NabzramIcon className="h-7 w-7" />
                    <h1 className="text-xl font-bold tracking-wider text-foreground">Nabzram</h1>
                </div>
                <div className="flex items-center space-x-2">
                    <button 
                        onClick={() => setIsSettingsModalOpen(true)} 
                        className="p-2 text-muted-foreground hover:text-foreground rounded-full transition-colors"
                        aria-label="Open settings"
                    >
                        <CogIcon className="h-5 w-5" />
                    </button>
                    <button
                        onClick={handleMinimize}
                        className="p-2 text-muted-foreground hover:text-foreground rounded-full transition-colors"
                        aria-label="Minimize application"
                    >
                        <MinimizeIcon className="h-5 w-5" />
                    </button>
                    <button
                        onClick={handleClose}
                        className="p-2 text-muted-foreground hover:text-destructive rounded-full transition-colors"
                        aria-label="Close application"
                    >
                        <XIcon className="h-5 w-5" />
                    </button>
                </div>
            </div>
            
            {renderContent()}

            {/* Modals */}
            {isAddModalOpen && (
                <AddSubscriptionModal
                    onClose={() => setIsAddModalOpen(false)}
                    onAddSuccess={onAddSubscriptionSuccess}
                />
            )}
            {isSettingsModalOpen && (
                <SettingsModal 
                    onClose={() => setIsSettingsModalOpen(false)} 
                    onSaveSuccess={onSettingsSaveSuccess}
                />
            )}
            {isLogsModalOpen && (
                <LogStreamModal onClose={() => setIsLogsModalOpen(false)} />
            )}
            {isUpdateModalOpen && (
                <UpdateModal 
                    onClose={() => setIsUpdateModalOpen(false)}
                    onUpdateSuccess={onUpdateSuccess}
                />
            )}
        </div>
    );
};

export default App;