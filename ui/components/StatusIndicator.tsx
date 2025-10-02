import React, { useState, useEffect, useRef } from 'react';
import { ServerStatus, ServerStatusResponse, SystemInfo } from '../types';
import { PowerIcon, ClockIcon } from './icons';

interface StatusIndicatorProps {
    status: ServerStatusResponse | null;
    xrayStatus: SystemInfo | null;
    isConnecting: boolean;
    onConnect: () => void;
    onStop: () => void;
    onOpenUpdates: () => void;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ 
    status, 
    xrayStatus, 
    isConnecting, 
    onConnect, 
    onStop, 
    onOpenUpdates,
}) => {
    const [duration, setDuration] = useState('');
    const [isFreshlyConnected, setIsFreshlyConnected] = useState(false);
    
    const isConnected = status?.status === ServerStatus.RUNNING;
    const prevIsConnected = useRef(isConnected);

    useEffect(() => {
        if (!prevIsConnected.current && isConnected) {
            setIsFreshlyConnected(true);
            const timer = setTimeout(() => {
                setIsFreshlyConnected(false);
            }, 2000); // Animate for 2 seconds

            return () => clearTimeout(timer);
        }
        prevIsConnected.current = isConnected;
    }, [isConnected]);

    useEffect(() => {
        let intervalId: number | undefined;

        if (isConnected && status?.start_time) {
            const startTime = new Date(status.start_time);

            if (isNaN(startTime.getTime())) {
                setDuration('');
                return;
            }

            const updateDuration = () => {
                const now = new Date();
                const diffSeconds = Math.max(0, Math.floor((now.getTime() - startTime.getTime()) / 1000));
                
                const hours = Math.floor(diffSeconds / 3600).toString().padStart(2, '0');
                const minutes = Math.floor((diffSeconds % 3600) / 60).toString().padStart(2, '0');
                const seconds = (diffSeconds % 60).toString().padStart(2, '0');
                
                setDuration(`${hours}:${minutes}:${seconds}`);
            };

            updateDuration();
            intervalId = window.setInterval(updateDuration, 1000);
        } else {
            setDuration('');
        }

        return () => {
            if (intervalId) {
                clearInterval(intervalId);
            }
        };
    }, [isConnected, status?.start_time]);
    
    const getStatusText = () => {
        if (isConnecting) return 'Connecting...';
        if (!status) return 'Checking Status...';
        switch (status.status) {
            case ServerStatus.RUNNING: return `Connected`;
            case ServerStatus.STOPPED: return 'Not Connected';
            case ServerStatus.ERROR: return 'Connection Error';
            default: return 'Unknown Status';
        }
    };

    const handleMainButtonClick = () => {
        if (isConnected) {
            onStop();
        } else {
            onConnect();
        }
    };

    const getButtonStateClasses = () => {
        if (isConnecting) {
            return 'bg-muted text-foreground animate-pulse cursor-wait';
        }
        if (isConnected) {
            const animationClass = isFreshlyConnected ? 'animate-fast-pulse' : '';
            return `bg-success text-primary-foreground shadow-lg shadow-success/40 hover:bg-success/90 ${animationClass}`;
        }
        return 'bg-secondary text-secondary-foreground shadow-md hover:bg-secondary/80';
    }

    const getButtonContent = () => {
        if (isConnecting) {
            return <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-primary"></div>;
        }
        return <PowerIcon className="h-12 w-12" />;
    };

    return (
        <div className="bg-card border border-border rounded-xl p-4 md:p-5 shadow-sm mb-8 flex flex-col sm:flex-row items-center justify-between space-y-4 sm:space-y-0 sm:space-x-6 transition-all duration-300 ease-out">
            <div className="flex-shrink-0">
                <button
                    onClick={handleMainButtonClick}
                    disabled={isConnecting}
                    className={`h-24 w-24 rounded-full flex items-center justify-center transition-all duration-200 ${getButtonStateClasses()}`}
                    aria-label={isConnected ? 'Disconnect' : 'Connect'}
                >
                    {getButtonContent()}
                </button>
            </div>
            <div className="flex-1 w-full text-center sm:text-left flex flex-col items-center sm:items-start">
                <h2 className={`text-2xl font-bold text-foreground`}>
                    {getStatusText()}
                </h2>

                <p className="text-muted-foreground text-sm truncate max-w-full mt-1.5 h-5">
                   {isConnected ? (status?.remarks) : (isConnecting ? '' : 'Click the power button to auto-connect')}
                </p>
                
                <div className="mt-2 flex flex-col items-center sm:items-start gap-y-1 w-full">
                    {/* Animated Duration */}
                    <div
                        className={`transition-all duration-300 ease-out overflow-hidden ${isConnected && duration ? 'max-h-8 opacity-100' : 'max-h-0 opacity-0'}`}
                        aria-hidden={!isConnected || !duration}
                    >
                        <div className="flex items-center text-sm text-foreground/90 font-mono bg-muted/60 px-2 py-0.5 rounded-md">
                            <ClockIcon className="h-4 w-4 mr-1.5" />
                            <span>{duration}</span>
                        </div>
                    </div>

                    {/* Animated Allocated Ports */}
                    <div
                        className={`transition-all duration-300 ease-out overflow-hidden ${isConnected && status?.allocated_ports && status.allocated_ports.length > 0 ? 'max-h-8 opacity-100' : 'max-h-0 opacity-0'}`}
                        aria-hidden={!isConnected || !status?.allocated_ports || status.allocated_ports.length === 0}
                    >
                        <p className="text-muted-foreground text-xs font-mono">
                            {status?.allocated_ports?.map(p => `${p.protocol.toUpperCase()}: ${p.port}`).join(' | ')}
                        </p>
                    </div>

                    {/* Xray Status */}
                    {xrayStatus && (
                        <div
                            onClick={onOpenUpdates}
                            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full transition-colors cursor-pointer bg-success/10 text-success hover:opacity-80"
                        >
                            <span className="h-2 w-2 rounded-full bg-success"></span>
                            <span className="text-xs font-mono">
                                Xray {xrayStatus.version}
                            </span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default StatusIndicator;