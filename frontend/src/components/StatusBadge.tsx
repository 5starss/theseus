import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: 'ACTIVE' | 'INACTIVE';
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center px-[9px] py-[3px] rounded-[2px] border text-[10px] font-bold uppercase",
        status === 'ACTIVE'
          ? "bg-[rgba(34,197,94,0.1)] border-[rgba(34,197,94,0.2)] text-[#4ade80]"
          : "bg-[rgba(239,68,68,0.1)] border-[rgba(239,68,68,0.2)] text-[#f87171]",
        className
      )}
    >
      {status}
    </span>
  );
}
