import React, { useState } from 'react';

export interface StockLogoProps {
    ticker: string;
    name: string;
    className?: string;
    fallbackClassName?: string;
}

const getStockIconColor = (name: string) => {
    const colors = [
        'bg-[#155dfc]',
        'bg-[#fb2c36]',
        'bg-[#2b7fff]',
        'bg-[#101828]',
        'bg-[#6a7282]',
    ];
    // 이름이 없을 경우 대비
    if (!name) return colors[0];
    return colors[name.length % colors.length];
};

export const StockLogo: React.FC<StockLogoProps> = ({ 
    ticker, 
    name, 
    className = "w-10 h-10 rounded-full", 
    fallbackClassName = "text-white font-bold" 
}) => {
    const [error, setError] = useState(false);

    if (error || !ticker) {
        return (
            <div className={`flex items-center justify-center shrink-0 ${getStockIconColor(name)} ${className} ${fallbackClassName}`}>
                {name ? name.charAt(0) : 'S'}
            </div>
        );
    }

    return (
        <img 
            src={`/icons/stocks/${ticker}.png`} 
            alt={`${name} logo`} 
            className={`object-cover shrink-0 ${className}`} 
            onError={() => setError(true)} 
        />
    );
};
