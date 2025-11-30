
import React, { useState, useEffect } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { useToast } from '../contexts/ToastContext';

interface JsonEditorModalProps {
    subscriptionId: string;
    serverId: string;
    serverName: string;
    onClose: () => void;
}

const JsonEditorModal: React.FC<JsonEditorModalProps> = ({ subscriptionId, serverId, serverName, onClose }) => {
    const [jsonContent, setJsonContent] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const { addToast } = useToast();

    useEffect(() => {
        const fetchJson = async () => {
            try {
                const response = await api.getServerJson(subscriptionId, serverId);
                setJsonContent(response.json_config);
            } catch (err) {
                const message = err instanceof Error ? err.message : 'Failed to load JSON config';
                addToast(message, 'error');
                onClose();
            } finally {
                setIsLoading(false);
            }
        };
        fetchJson();
    }, [subscriptionId, serverId, addToast, onClose]);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            // Validate JSON locally before sending
            try {
                JSON.parse(jsonContent);
            } catch (e) {
                throw new Error('Invalid JSON format');
            }

            const response = await api.updateServerJson(subscriptionId, serverId, jsonContent);
            addToast('Configuration updated successfully', 'success');
            
            if (response.restart_result.action === 'restarted') {
                 addToast('Server restarted with new configuration', 'info');
            } else if (response.restart_result.action === 'no_action' && response.restart_result.was_running === false) {
                 // Nothing special, just saved
            }
            
            onClose();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to save configuration';
            addToast(message, 'error');
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Modal title={`Config: ${serverName}`} onClose={onClose} bodyClassName="flex flex-col h-[80vh]">
            {isLoading ? (
                 <div className="flex-1 flex justify-center items-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
                </div>
            ) : (
                <div className="flex-1 flex flex-col min-h-0">
                    <div className="flex-1 relative">
                        <textarea
                            className="absolute inset-0 w-full h-full bg-input border border-border rounded-md p-3 font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                            value={jsonContent}
                            onChange={(e) => setJsonContent(e.target.value)}
                            spellCheck={false}
                        />
                    </div>
                    <div className="flex justify-end pt-4 space-x-2 shrink-0">
                        <button
                            onClick={onClose}
                            className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors"
                            disabled={isSaving}
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            className="bg-primary text-primary-foreground font-bold py-2 px-4 rounded-md hover:bg-primary/90 disabled:opacity-50 transition-colors"
                            disabled={isSaving}
                        >
                            {isSaving ? 'Saving...' : 'Save & Restart'}
                        </button>
                    </div>
                </div>
            )}
        </Modal>
    );
};

export default JsonEditorModal;
