
import React, { useState, useEffect, useRef } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { LogEntry } from '../types';

interface LogStreamModalProps {
    onClose: () => void;
}

const LogStreamModal: React.FC<LogStreamModalProps> = ({ onClose }) => {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const logContainerRef = useRef<HTMLDivElement>(null);
    const sinceMsRef = useRef<number | null>(null);
    const shouldStickToBottom = useRef(true);

    // Initial fetch
    useEffect(() => {
        const fetchInitialLogs = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const response = await api.getLogSnapshot(200);
                setLogs(response.logs);
                // Set the starting point for polling to be right after the snapshot
                sinceMsRef.current = Date.now();
            } catch (err) {
                const message = err instanceof Error ? err.message : "Failed to load initial logs.";
                setError(message);
            } finally {
                setIsLoading(false);
            }
        };

        fetchInitialLogs();
    }, []);

    // Polling effect
    useEffect(() => {
        if (isLoading || error) {
            return; // Don't start polling until initial load is done and successful
        }

        const poll = async () => {
            try {
                const response = await api.getLogStreamBatch(sinceMsRef.current ?? undefined, 200);
                if (response.logs && response.logs.length > 0) {
                    setLogs(prevLogs => [...prevLogs, ...response.logs]);
                }
                if (response.next_since_ms) {
                    sinceMsRef.current = response.next_since_ms;
                }
            } catch (err) {
                console.error("Log polling error:", err);
                // Can add a visual indicator for polling errors if needed
            }
        };

        const intervalId = setInterval(poll, 1500);

        return () => clearInterval(intervalId);
    }, [isLoading, error]);

    // Auto-scroll effect
    useEffect(() => {
        const container = logContainerRef.current;
        if (container && shouldStickToBottom.current) {
            container.scrollTop = container.scrollHeight;
        }
    }, [logs]);

    const handleScroll = () => {
        const container = logContainerRef.current;
        if (container) {
            const threshold = 20; // A small buffer in pixels
            const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= threshold;
            shouldStickToBottom.current = atBottom;
        }
    };

    const renderLogs = () => {
        if (isLoading) {
            return (
                <div className="flex justify-center items-center h-full">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
                </div>
            );
        }
        if (error) {
            return <div className="text-destructive text-center">{error}</div>;
        }
        if (logs.length === 0) {
            return <div className="text-muted-foreground text-center">No log entries found.</div>;
        }

        return logs.map((log, index) => (
             <div key={index} className="flex items-start">
                <span className="text-primary/70 pr-3 whitespace-nowrap">{new Date(log.timestamp).toLocaleTimeString()}</span>
                <span className="whitespace-pre-wrap break-all">{log.message}</span>
             </div>
        ));
    };

    return (
        <Modal title="Live Logs" onClose={onClose}>
            <div
                ref={logContainerRef}
                onScroll={handleScroll}
                className="bg-background text-muted-foreground font-mono text-xs p-4 rounded-md h-96 overflow-y-auto border border-border space-y-1"
                aria-live="polite"
                aria-atomic="false"
            >
                {renderLogs()}
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
