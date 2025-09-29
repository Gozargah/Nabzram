import React, { useState, useEffect, useRef } from 'react';
import Modal from './Modal';
import { API_BASE_URL } from '../constants';

interface LogStreamModalProps {
    onClose: () => void;
}

type LogLevel = 'info' | 'log' | 'error' | 'system';

interface LogEntry {
    id: number;
    message: string;
    level: LogLevel;
}

const LogStreamModal: React.FC<LogStreamModalProps> = ({ onClose }) => {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const logContainerRef = useRef<HTMLDivElement>(null);
    const logIdCounter = useRef(0);

    useEffect(() => {
        const addLog = (message: string, level: LogLevel) => {
            setLogs(prev => [...prev, { id: logIdCounter.current++, message, level }]);
        };

        addLog('Connecting to log stream...', 'system');
        const eventSource = new EventSource(`${API_BASE_URL}/logs/stream`);
        
        eventSource.onopen = () => {
            setIsConnected(true);
            setLogs(prev => prev.filter(l => !l.message.includes('Connecting')));
            addLog('Connection established. Waiting for logs...', 'system');
        };

        const handleEvent = (event: Event, level: LogLevel) => {
            // FIX: Cast event to MessageEvent. EventSource's addEventListener provides a generic
            // Event type, but for server-sent events, it's a MessageEvent with a 'data' property.
            const messageEvent = event as MessageEvent;
            try {
                const data = JSON.parse(messageEvent.data);
                const message = data.timestamp
                    ? `[${new Date(data.timestamp).toLocaleTimeString()}] ${data.message}`
                    : data.message;
                addLog(message, level);
            } catch (e) {
                addLog(messageEvent.data, level); // Fallback for non-JSON data
            }
        };

        eventSource.addEventListener('log', (event) => handleEvent(event, 'log'));
        eventSource.addEventListener('info', (event) => handleEvent(event, 'info'));
        eventSource.addEventListener('error', (event) => handleEvent(event, 'error'));
        
        eventSource.onerror = () => {
            if (isConnected) { // Only show error if we were previously connected
                addLog('Connection lost. Please close and reopen to reconnect.', 'system');
            } else {
                 addLog('Failed to connect to log stream.', 'system');
            }
            setIsConnected(false);
            eventSource.close();
        };
        
        return () => {
            eventSource.close();
        };
    }, [isConnected]);

    useEffect(() => {
        if (logContainerRef.current) {
            logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
    }, [logs]);

    const getLogColor = (level: LogLevel) => {
        switch (level) {
            case 'error': return 'text-destructive';
            case 'info': return 'text-primary';
            case 'system': return 'text-muted-foreground/70';
            case 'log':
            default: return 'text-muted-foreground';
        }
    };

    return (
        <Modal title="Live Logs" onClose={onClose}>
            <div 
                ref={logContainerRef} 
                className="bg-background text-muted-foreground font-mono text-xs p-4 rounded-md h-96 overflow-y-auto border border-border"
                aria-live="polite"
                aria-atomic="false"
            >
                {logs.map((log) => (
                    <div key={log.id} className={`whitespace-pre-wrap ${getLogColor(log.level)}`}>{log.message}</div>
                ))}
            </div>
             <div className="flex justify-end pt-4">
                    <button 
                        onClick={onClose}
                        className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors"
                    >
                        Close
                    </button>
                </div>
        </Modal>
    );
};

export default LogStreamModal;