import React, { useState } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { useToast } from '../contexts/ToastContext';
import { SubscriptionImportItem } from '../types';

interface ImportConfirmModalProps {
    subscriptions: SubscriptionImportItem[];
    onClose: () => void;
    onImportSuccess: () => void;
}

const ImportConfirmModal: React.FC<ImportConfirmModalProps> = ({ subscriptions, onClose, onImportSuccess }) => {
    const [isImporting, setIsImporting] = useState(false);
    const { addToast } = useToast();

    const handleConfirm = async () => {
        setIsImporting(true);
        try {
            const response = await api.importSubscriptions(subscriptions);
            addToast(response.message, 'success');
            onImportSuccess();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to import subscriptions';
            addToast(message, 'error');
        } finally {
            setIsImporting(false);
            // No need to call onClose here as onImportSuccess should close the parent modal
        }
    };

    return (
        <Modal title="Confirm Import" onClose={onClose}>
            <div className="text-foreground">
                <p className="mb-4">
                    You are about to import <span className="font-bold">{subscriptions.length}</span> subscription(s). This will add them to your existing list. Are you sure you want to continue?
                </p>
                <div className="max-h-48 overflow-y-auto bg-muted/50 p-3 rounded-md border border-border mb-6">
                    <ul className="space-y-1 text-sm text-muted-foreground list-disc list-inside">
                        {subscriptions.map((sub, index) => (
                            <li key={index} className="truncate" title={sub.name}>{sub.name}</li>
                        ))}
                    </ul>
                </div>
                <div className="flex justify-end space-x-4">
                    <button
                        onClick={onClose}
                        disabled={isImporting}
                        className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleConfirm}
                        disabled={isImporting}
                        className="bg-primary text-primary-foreground font-bold py-2 px-4 rounded-md hover:bg-primary/90 disabled:bg-primary/70 disabled:cursor-not-allowed transition-colors"
                    >
                        {isImporting ? 'Importing...' : 'Confirm Import'}
                    </button>
                </div>
            </div>
        </Modal>
    );
};

export default ImportConfirmModal;