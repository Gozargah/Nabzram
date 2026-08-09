import React, { useState } from 'react';
import Modal from './Modal';
import * as api from '../services/api';
import { useToast } from '../contexts/ToastContext';

export interface TunXrayUpdateRequest {
    subscriptionId: string;
    serverId: string;
    requiredVersion: string;
    currentVersion: string | null;
    remarks?: string;
}

interface TunXrayUpdateModalProps {
    request: TunXrayUpdateRequest;
    onClose: () => void;
    onSuccess: () => void;
}

const TunXrayUpdateModal: React.FC<TunXrayUpdateModalProps> = ({ request, onClose, onSuccess }) => {
    const [phase, setPhase] = useState<'idle' | 'updating' | 'connecting'>('idle');
    const { addToast } = useToast();
    const isBusy = phase !== 'idle';

    const handleUpdateAndConnect = async () => {
        setPhase('updating');
        try {
            const updateResponse = await api.updateXray({ version: request.requiredVersion });
            addToast(updateResponse.message, 'success');

            setPhase('connecting');
            await api.startServer(request.subscriptionId, request.serverId);
            const label = request.remarks ? `Connected to ${request.remarks}` : 'Connected successfully';
            addToast(label, 'success');
            onSuccess();
            onClose();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to update Xray or connect';
            addToast(message, 'error');
        } finally {
            setPhase('idle');
        }
    };

    return (
        <Modal title="Xray Update Required" onClose={onClose} closeDisabled={isBusy}>
            <div className="text-foreground space-y-5">
                {isBusy ? (
                    <div className="flex flex-col items-center justify-center py-8 space-y-4">
                        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-primary"></div>
                        <div className="text-center space-y-1">
                            <p className="font-medium">
                                {phase === 'updating' ? 'Updating Xray...' : 'Connecting...'}
                            </p>
                            <p className="text-sm text-muted-foreground">
                                {phase === 'updating'
                                    ? `Installing ${request.requiredVersion}. Administrator approval may be required.`
                                    : 'Starting the server. Administrator approval may be required for TUN mode.'}
                            </p>
                        </div>
                    </div>
                ) : (
                    <>
                        <p>
                            TUN mode requires Xray <span className="font-mono">{request.requiredVersion}</span> or newer
                            {request.currentVersion ? (
                                <>
                                    {' '}(current: <span className="font-mono">{request.currentVersion}</span>)
                                </>
                            ) : null}
                            .
                        </p>
                        <p className="text-sm text-muted-foreground">
                            Update Xray first, then the connection will start. System paths and TUN mode may prompt for administrator rights.
                        </p>
                        <div className="flex justify-end space-x-3 pt-2">
                            <button
                                type="button"
                                onClick={onClose}
                                className="bg-secondary text-secondary-foreground font-bold py-2 px-4 rounded-md hover:bg-secondary/80 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleUpdateAndConnect}
                                className="bg-primary text-primary-foreground font-bold py-2 px-4 rounded-md hover:bg-primary/90 transition-colors"
                            >
                                Update & Connect
                            </button>
                        </div>
                    </>
                )}
            </div>
        </Modal>
    );
};

export default TunXrayUpdateModal;
