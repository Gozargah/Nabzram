import React, { useState } from 'react';
import { Subscription, Server, ServerStatusResponse, ServerStatus, ServerTestResult } from '../types';
import * as api from '../services/api';
import { TrashIcon, PencilIcon, RefreshIcon, ChevronRightIcon, PlusIcon, ConnectIcon, PingIcon, LightningBoltIcon } from './icons';
import EditSubscriptionModal from './EditSubscriptionModal';
import ConfirmDeleteModal from './ConfirmDeleteModal';
import { useToast } from '../contexts/ToastContext';
import { formatBytes } from './utils';

// === Helper Functions ===
function formatTimeRemaining(expireValue: string | null | number): string {
    if (!expireValue || expireValue === 0 || expireValue === '0') {
      return 'Never';
    }
  
    let expireDate: Date;
    if (typeof expireValue === 'string') {
        expireDate = new Date(expireValue);
        if (isNaN(expireDate.getTime())) {
            const ts = Number(expireValue) * 1000;
            if (!isNaN(ts) && ts > 0) {
                 expireDate = new Date(ts);
            } else {
                return 'Invalid date';
            }
        }
    } else { // is number
         expireDate = new Date(expireValue * 1000);
    }
  
    if (isNaN(expireDate.getTime())) {
      return 'Invalid date';
    }
  
    const now = new Date();
    const diff = expireDate.getTime() - now.getTime();
  
    if (diff <= 0) {
      return 'Expired';
    }
  
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days > 0) return `${days}d`;
  
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours > 0) return `${hours}h`;
  
    const minutes = Math.floor(diff / (1000 * 60));
    if (minutes > 0) return `${minutes}m`;
    
    return '<1m';
}

// === PingResult component ===
const PingResult: React.FC<{ result: ServerTestResult }> = ({ result }) => {
    if (!result.success || result.ping_ms === null) {
        return <span className="text-destructive text-xs font-mono" title={result.error || 'Test failed'}>Timeout</span>;
    }
    return <span className="text-success text-xs font-mono">{result.ping_ms} ms</span>;
};

// === ServerItem component ===
interface ServerItemProps {
    server: Server;
    subscriptionId: string;
    isConnected: boolean;
    onConnect: () => void;
    testResult: ServerTestResult | null;
}

const ServerItem: React.FC<ServerItemProps> = ({ server, subscriptionId, isConnected, onConnect, testResult }) => {
    const [isConnecting, setIsConnecting] = useState(false);
    const { addToast } = useToast();
    
    const handleConnect = async () => {
        setIsConnecting(true);
        try {
            await api.startServer(subscriptionId, server.id);
            addToast(`Connected to ${server.remarks}`, 'success');
            onConnect();
        } catch (err) {
            const detail = err instanceof Error ? err.message : 'An unknown error occurred.';
            addToast(`Failed to connect: ${detail}`, 'error');
        } finally {
            setIsConnecting(false);
        }
    };
    
    const buttonStyle = isConnected
        ? 'bg-success text-success-foreground cursor-default'
        : 'bg-secondary text-secondary-foreground hover:bg-secondary/80';

    return (
        <div className={`bg-muted/50 p-3 rounded-md mb-2 flex items-center justify-between transition-all ${isConnected ? 'border-l-4 border-success' : 'border-l-4 border-transparent'}`}>
            <div className="flex-1 flex items-center min-w-0 mr-2">
                <p className="flex-1 text-muted-foreground truncate text-sm">{server.remarks}</p>
            </div>
            <div className="flex items-center space-x-3">
                {testResult && <PingResult result={testResult} />}
                <button
                    onClick={handleConnect}
                    disabled={isConnected || isConnecting}
                    className={`flex items-center justify-center w-24 h-9 rounded-md font-semibold transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed ${buttonStyle}`}
                >
                    {isConnecting ? (
                         <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-foreground"></div>
                    ) : isConnected ? (
                        'Connected'
                    ) : (
                        <div className="flex items-center space-x-2">
                            <ConnectIcon className="h-4 w-4"/>
                            <span>Connect</span>
                        </div>
                    )}
                </button>
            </div>
        </div>
    );
};


// === SubscriptionItem component ===
interface SubscriptionItemProps {
    subscription: Subscription;
    refreshList: () => void;
    currentStatus: ServerStatusResponse | null;
    onConnect: () => void;
}

const SubscriptionItem: React.FC<SubscriptionItemProps> = ({ subscription, refreshList, currentStatus, onConnect }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [servers, setServers] = useState<Server[] | null>(null);
    const [isLoadingServers, setIsLoadingServers] = useState(false);
    const [serverError, setServerError] = useState<string | null>(null);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [testResults, setTestResults] = useState<Record<string, ServerTestResult>>({});
    const [isTesting, setIsTesting] = useState(false);
    const [isAutoConnecting, setIsAutoConnecting] = useState(false);
    const { addToast } = useToast();

    const fetchServers = async () => {
        setIsLoadingServers(true);
        setServerError(null);
        try {
            const details = await api.getSubscriptionDetails(subscription.id);
            setServers(details.servers);
        } catch (err) {
            setServerError(err instanceof Error ? err.message : 'Failed to load servers.');
        } finally {
            setIsLoadingServers(false);
        }
    };

    const handleToggleExpand = () => {
        const nextState = !isExpanded;
        setIsExpanded(nextState);
        if (nextState && !servers) {
            fetchServers();
        }
    };
    
    const handleRefresh = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsRefreshing(true);
        try {
            await api.refreshSubscriptionServers(subscription.id);
            addToast('Subscription refreshed successfully.', 'success');
            await refreshList();
            if (isExpanded) {
                await fetchServers();
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to refresh';
            addToast(message, 'error');
        } finally {
            setIsRefreshing(false);
        }
    };

    const handleDeleteClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsDeleteModalOpen(true);
    };

    const handleConfirmDelete = async () => {
        setIsDeleting(true);
        try {
            await api.deleteSubscription(subscription.id);
            addToast('Subscription deleted.', 'success');
            refreshList();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to delete';
            addToast(message, 'error');
            setIsDeleting(false);
        }
    };
    
    const onEditSuccess = () => {
        addToast('Subscription updated.', 'success');
        setIsEditModalOpen(false);
        refreshList();
    };

    const handleTestServers = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsTesting(true);
        setTestResults({});
        addToast(`Testing servers for ${subscription.name}...`, 'info');
        try {
            const response = await api.testSubscriptionServers(subscription.id);
            const resultsMap = response.results.reduce((acc, result) => {
                acc[result.server_id] = result;
                return acc;
            }, {} as Record<string, ServerTestResult>);
            setTestResults(resultsMap);
            addToast(`Testing complete. ${response.successful_tests}/${response.total_servers} servers responded.`, 'success');
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to test servers';
            addToast(message, 'error');
        } finally {
            setIsTesting(false);
        }
    };

    const handleAutoConnect = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsAutoConnecting(true);
        setTestResults({});
        addToast('Finding the fastest server...', 'info');
        
        if (!isExpanded) {
            setIsExpanded(true);
        }
        if (!servers) {
           await fetchServers();
        }

        try {
            const response = await api.testSubscriptionServers(subscription.id);
            
            const resultsMap = response.results.reduce((acc, result) => {
                acc[result.server_id] = result;
                return acc;
            }, {} as Record<string, ServerTestResult>);
            setTestResults(resultsMap);

            const successfulTests = response.results
                .filter(r => r.success && r.ping_ms !== null && r.ping_ms > 0)
                .sort((a, b) => a.ping_ms! - b.ping_ms!);

            if (successfulTests.length === 0) {
                addToast('Auto-connect failed: No responsive servers found.', 'error');
                setIsAutoConnecting(false);
                return;
            }

            const bestServer = successfulTests[0];
            await api.startServer(subscription.id, bestServer.server_id);
            addToast(`Auto-connected to ${bestServer.remarks} (${bestServer.ping_ms}ms)`, 'success');
            onConnect();
        } catch (err) {
            const detail = err instanceof Error ? err.message : 'An unknown error occurred.';
            addToast(`Failed to auto-connect: ${detail}`, 'error');
        } finally {
            setIsAutoConnecting(false);
        }
    };
    
    return (
        <>
            <div className="bg-card rounded-lg mb-3 overflow-hidden transition-all duration-200">
                <div 
                    className="p-4 flex items-center justify-between cursor-pointer hover:bg-accent/20 transition-colors"
                    onClick={handleToggleExpand}
                    aria-expanded={isExpanded}
                >
                    <div className="flex-1 min-w-0 pr-2">
                        <div className="flex items-center space-x-2">
                            <p className="text-card-foreground font-semibold truncate">{subscription.name}</p>
                            {subscription.user_info?.expire && (() => {
                                const timeRemaining = formatTimeRemaining(subscription.user_info.expire);
                                let text: string | null = null;
                                let colorClass = 'text-muted-foreground bg-muted';
                    
                                if (timeRemaining === 'Expired') {
                                    text = 'Expired';
                                    colorClass = 'text-destructive-foreground bg-destructive/80 font-semibold';
                                } else if (timeRemaining !== 'Never' && timeRemaining !== 'Invalid date') {
                                    text = `expires in ${timeRemaining}`;
                                }

                                if (!text) return null;

                                return (
                                    <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${colorClass}`}>
                                        {text}
                                    </span>
                                );
                            })()}
                        </div>
                        <div className="text-muted-foreground text-xs mt-1.5">
                            {subscription.user_info && (() => {
                                const { used_traffic, total } = subscription.user_info;
                                if (used_traffic > 0 || (total && total > 0)) {
                                    const used = formatBytes(used_traffic);
                                    const totalStr = total ? ` / ${formatBytes(total)}` : ' / ∞';
                                    return <span key="data-usage">{used}{totalStr}</span>;
                                }
                                return null;
                            })()}
                        </div>
                    </div>

                    <div className="flex items-center ml-2 flex-shrink-0">
                        <button onClick={handleAutoConnect} disabled={isAutoConnecting || isTesting} className="p-2 text-muted-foreground hover:text-foreground rounded-full disabled:text-muted-foreground/50 disabled:cursor-not-allowed" title="Auto-connect to fastest server">
                            <LightningBoltIcon className={`h-5 w-5 ${isAutoConnecting ? 'animate-fast-pulse' : ''}`} />
                        </button>
                        <button onClick={handleTestServers} disabled={isTesting || isAutoConnecting} className="p-2 text-muted-foreground hover:text-foreground rounded-full disabled:text-muted-foreground/50 disabled:cursor-not-allowed" title="Test all servers latency">
                           <PingIcon className="h-5 w-5" isAnimating={isTesting} />
                        </button>
                        <button onClick={handleRefresh} disabled={isRefreshing} className="p-2 text-muted-foreground hover:text-foreground rounded-full" title="Refresh subscription from URL">
                            <RefreshIcon className="h-5 w-5" spin={isRefreshing} />
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); setIsEditModalOpen(true); }} className="p-2 text-muted-foreground hover:text-foreground rounded-full" title="Edit subscription name">
                            <PencilIcon className="h-5 w-5" />
                        </button>
                        <button onClick={handleDeleteClick} className="p-2 text-destructive hover:text-destructive/90 rounded-full" title="Delete subscription">
                            <TrashIcon className="h-5 w-5" />
                        </button>
                        <ChevronRightIcon className={`h-6 w-6 text-muted-foreground/80 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                    </div>
                </div>

                <div className={`transition-[max-height] duration-200 ease-in-out overflow-hidden ${isExpanded ? 'max-h-[1000px]' : 'max-h-0'}`}>
                    <div className={`px-4 pb-2 pt-4 bg-background/50 transition-all duration-200 ease-in-out transform ${isExpanded ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2'}`}>
                        {isLoadingServers && (
                            <div className="flex justify-center items-center py-4">
                               <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
                            </div>
                        )}
                        {serverError && <p className="text-destructive text-center py-4">{serverError}</p>}
                        {servers && servers.length > 0 && servers.map(server => (
                             <ServerItem
                                key={server.id}
                                server={server}
                                subscriptionId={subscription.id}
                                isConnected={currentStatus?.status === ServerStatus.RUNNING && currentStatus?.server_id === server.id}
                                onConnect={onConnect}
                                testResult={testResults[server.id] || null}
                            />
                        ))}
                         {servers && servers.length === 0 && (
                            <div className="text-center text-muted-foreground py-4">
                                <p>No servers found in this subscription.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {isEditModalOpen && <EditSubscriptionModal 
                onClose={() => setIsEditModalOpen(false)} 
                onEditSuccess={onEditSuccess} 
                currentName={subscription.name}
                currentUrl={subscription.url}
                subscriptionId={subscription.id}
            />}
            {isDeleteModalOpen && <ConfirmDeleteModal 
                subscriptionName={subscription.name}
                onClose={() => setIsDeleteModalOpen(false)}
                onConfirm={handleConfirmDelete}
                isDeleting={isDeleting}
            />}
        </>
    );
};


// === SubscriptionList component (modified props) ===
interface SubscriptionListProps {
    subscriptions: Subscription[];
    onAdd: () => void;
    refreshList: () => void;
    currentStatus: ServerStatusResponse | null;
    onConnect: () => void;
}

const SubscriptionList: React.FC<SubscriptionListProps> = ({ subscriptions, onAdd, refreshList, currentStatus, onConnect }) => {
    return (
        <div>
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold text-foreground">Subscriptions</h2>
                <button onClick={onAdd} className="bg-primary text-primary-foreground p-2 rounded-full hover:bg-primary/90 transition-colors" aria-label="Add new subscription">
                    <PlusIcon className="h-6 w-6" />
                </button>
            </div>
            {subscriptions.length > 0 ? (
                subscriptions.map(sub => (
                    <SubscriptionItem 
                        key={sub.id} 
                        subscription={sub} 
                        refreshList={refreshList}
                        currentStatus={currentStatus}
                        onConnect={onConnect}
                    />
                ))
            ) : (
                <div className="text-center text-muted-foreground py-10">
                    <p>No subscriptions found.</p>
                    <p>Click the '+' icon to add one.</p>
                </div>
            )}
        </div>
    );
};

export default SubscriptionList;