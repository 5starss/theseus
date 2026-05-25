import { MessageSquare, Eye, Heart } from "lucide-react";
import { Link } from "react-router-dom";
import { format } from "date-fns";
import type { CommunityPostListItem } from "../../../types/community";
import { CommunityBadge } from "./CommunityBadge";

interface CommunityPostCardProps {
  post: CommunityPostListItem;
}

export function CommunityPostCard({ post }: CommunityPostCardProps) {
  return (
    <Link
      to={`/stock/${post.stockCode}/community/posts/${post.postId}`}
      className="block rounded-2xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 text-base font-bold text-slate-900">
            {post.title}
          </h3>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span className="font-semibold text-slate-800">
              {post.authorNickname}
            </span>
            <CommunityBadge isShareholder={post.isShareholder} />
            <span className="text-slate-300">|</span>
            <span>{format(new Date(post.createdAt), "yyyy.MM.dd HH:mm")}</span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3 text-xs font-semibold text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Eye className="size-3.5" />
            {post.viewCount}
          </span>
          <span className="inline-flex items-center gap-1">
            <MessageSquare className="size-3.5" />
            {post.commentCount}
          </span>
          <span
            className={`inline-flex items-center gap-1 ${
              post.likedByMe ? "text-rose-500" : ""
            }`}
          >
            <Heart className={`size-3.5 ${post.likedByMe ? "fill-current" : ""}`} />
            {post.likeCount}
          </span>
        </div>
      </div>
    </Link>
  );
}
