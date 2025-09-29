import React, { useState } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { useToast } from '../contexts/ToastContext';

interface AddSubscriptionModalProps {
    onClose: () => void;
    onAddSuccess: () => void;
}

const AddSubscriptionModal: React.FC<AddSubscriptionModalProps> = ({ onClose, onAddSuccess }) => {
    const [name, setName] = useState('');
    const [url, setUrl] = useState('');
    const [isAdding, setIsAdding] = useState(false);
    const { addToast } = useToast();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!name || !url) {
            addToast('Name and URL are required.', 'error');
            return;
        }
        setIsAdding(true);
        try {
            await api.createSubscription({ name, url });
            onAddSuccess();
        } catch(err) {
            const message = err instanceof Error ? err.message : 'Failed to add subscription';
            addToast(message, 'error');
        } finally {
            setIsAdding(false);
        }
    };

    return (
        <Modal title="Add Subscription" onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label htmlFor="name" className="block text-sm font-medium text-muted-foreground mb-1">Name</label>
                    <input
                        type="text"
                        id="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                        placeholder="My Subscription"
                        required
                    />
                </div>
                <div>
                    <label htmlFor="url" className="block text-sm font-medium text-muted-foreground mb-1">URL</label>
                    <input
                        type="url"
                        id="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        className="w-full bg-input border border-border rounded-md p-2 text-foreground focus:ring-2 focus:ring-ring focus:outline-none"
                        placeholder="https://example.com/sub"
                        required
                    />
                </div>
                <div className="flex justify-end pt-2">
                    <button 
                        type="submit" 
                        disabled={isAdding}
                        className="bg-primary text-primary-foreground font-bold py-2 px-4 rounded-md hover:bg-primary/90 disabled:bg-primary/50 disabled:cursor-not-allowed transition-colors"
                    >
                        {isAdding ? 'Adding...' : 'Add'}
                    </button>
                </div>
            </form>
        </Modal>
    );
};

export default AddSubscriptionModal;