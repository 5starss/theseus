interface CommunityBadgeProps {
  isShareholder: boolean;
}

export function CommunityBadge({ isShareholder }: CommunityBadgeProps) {
  if (!isShareholder) {
    return null;
  }

  return (
    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 ring-1 ring-emerald-200">
      주주
    </span>
  );
}
