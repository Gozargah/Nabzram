import React, { ReactNode, useState, useEffect } from 'react';

interface ModalProps {
    title: string;
    children: ReactNode;
    onClose: () => void;
    bodyClassName?: string;
}

const Modal: React.FC<ModalProps> = ({ title, children, onClose, bodyClassName }) => {
    const [isClosing, setIsClosing] = useState(false);

    const handleClose = () => {
        setIsClosing(true);
        // Match the duration in tailwind.config animation
        setTimeout(() => {
            onClose();
        }, 150);
    };

    // Handle Escape key press
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                handleClose();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, []);

    return (
        <div 
            className={`fixed inset-0 bg-background/80 backdrop-blur-sm flex justify-center items-center z-50 p-4 ${isClosing ? 'animate-fade-out' : 'animate-fade-in'}`}
            onMouseDown={handleClose} // Close on backdrop click
        >
            <div 
                className={`bg-card border border-border rounded-lg shadow-xl w-full max-w-md flex flex-col max-h-[90vh] ${isClosing ? 'animate-scale-out' : 'animate-scale-in'}`}
                onMouseDown={(e) => e.stopPropagation()} // Prevent closing when clicking inside modal
            >
                <div className="flex justify-between items-center p-4 border-b border-border flex-shrink-0">
                    <h2 className="text-xl font-semibold text-card-foreground">{title}</h2>
                    <button onClick={handleClose} className="text-muted-foreground hover:text-foreground transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div className={`p-6 overflow-y-auto ${bodyClassName ?? ''}`}>
                    {children}
                </div>
            </div>
        </div>
    );
};

export default Modal;
