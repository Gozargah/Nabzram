import React from 'react';
import { useToast } from '../contexts/ToastContext';
import { CheckCircleIcon, XCircleIcon, InformationCircleIcon } from './icons';

// FIX: Replaced JSX.Element with React.ReactNode to resolve namespace error.
const ICONS: Record<string, React.ReactNode> = {
    success: <CheckCircleIcon className="h-6 w-6 text-success" />,
    error: <XCircleIcon className="h-6 w-6 text-destructive" />,
    info: <InformationCircleIcon className="h-6 w-6 text-primary" />,
};

const TOAST_STYLES: Record<string, string> = {
    success: 'bg-card border-success/30 text-success',
    error: 'bg-card border-destructive/30 text-destructive',
    info: 'bg-card border-primary/30 text-primary',
}

const ToastContainer: React.FC = () => {
    const { toasts, removeToast } = useToast();

    if (!toasts.length) {
        return null;
    }

    return (
        <div className="fixed bottom-4 inset-x-0 z-[100] flex flex-col items-center space-y-3 px-4">
            {toasts.map((toast) => (
                 <div
                    key={toast.id}
                    onClick={() => removeToast(toast.id)}
                    className={`w-full max-w-sm flex items-start space-x-4 p-4 border rounded-lg shadow-lg bg-opacity-80 backdrop-blur-sm transition-all duration-200 animate-fade-in-up cursor-pointer ${TOAST_STYLES[toast.type]}`}
                    role="alert"
                >
                    <div className="flex-shrink-0">{ICONS[toast.type]}</div>
                    <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{toast.message}</p>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default ToastContainer;