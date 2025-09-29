import React from 'react';
import Modal from './Modal';

interface ConfirmDeleteModalProps {
    subscriptionName: string;
    onClose: () => void;
    onConfirm: () => void;
    isDeleting: boolean;
}

const ConfirmDeleteModal: React.FC<ConfirmDeleteModalProps> = ({ subscriptionName, onClose, onConfirm, isDeleting }) => {
    return (
        <Modal title="Confirm Deletion" onClose={onClose}>
            <div className="text-foreground">
                <p className="mb-6">Are you sure you want to delete the subscription "{subscriptionName}"? This action cannot be undone.</p>
                <div className="flex justify-end space-x-4">
                    <button
                        onClick={onClose}
                        disabled={isDeleting}
                        className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={isDeleting}
                        className="bg-destructive text-destructive-foreground font-bold py-2 px-4 rounded-md hover:bg-destructive/90 disabled:bg-destructive/70 disabled:cursor-not-allowed transition-colors"
                    >
                        {isDeleting ? 'Deleting...' : 'Delete'}
                    </button>
                </div>
            </div>
        </Modal>
    );
};

export default ConfirmDeleteModal;