import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MessageSquarePlus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { communityApi } from "../../../api/community";
import { useAuthStore } from "../../../store/useAuthStore";
import { getErrorMessage } from "../../../utils/errorMessages";
import type {
  CommunityPageResponse,
  CommunityPostListItem,
  CommunityPostSort,
} from "../../../types/community";
import { Button } from "../../ui/button";
import { CommunityPostCard } from "./CommunityPostCard";
import { ApiError } from "../../../api/client";

interface CommunityTabProps {
  stockCode: string;
  stockName: string;
}

export function CommunityTab({ stockCode, stockName }: CommunityTabProps) {
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const [sort, setSort] = useState<CommunityPostSort>("latest");
  const [postsPage, setPostsPage] =
    useState<CommunityPageResponse<CommunityPostListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPosts = useCallback(async () => {
    if (!stockCode) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await communityApi.getPosts(stockCode, 0, 20, sort);
      setPostsPage(response);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? getErrorMessage(error.code, error.message)
          : "커뮤니티 글을 불러오지 못했습니다.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [stockCode, sort]);

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  const handleRefresh = async () => {
    await loadPosts();
    toast.success("커뮤니티 목록을 새로고침했습니다.");
  };

  const posts = postsPage?.content ?? [];
  const sortOptions: Array<{ value: CommunityPostSort; label: string }> = [
    { value: "latest", label: "최신순" },
    { value: "likes", label: "좋아요순" },
    { value: "comments", label: "댓글순" },
    { value: "views", label: "조회수순" },
  ];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">커뮤니티</h2>
          <p className="mt-1 text-sm text-slate-500">
            {stockName || stockCode}에 대한 의견을 나눠보세요.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="size-4" />
            새로고침
          </Button>
          {isLoggedIn ? (
            <Button asChild size="sm" className="bg-[#155dfc] hover:bg-[#124bc9]">
              <Link to={`/stock/${stockCode}/community/posts/new`}>
                <MessageSquarePlus className="size-4" />
                글쓰기
              </Link>
            </Button>
          ) : (
            <Button asChild size="sm" variant="outline">
              <Link to="/login">로그인 후 글쓰기</Link>
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {sortOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setSort(option.value)}
            className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
              sort === option.value
                ? "border-blue-200 bg-blue-50 text-blue-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-slate-100"
              />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-8 text-center">
            <p className="text-sm font-medium text-red-700">{error}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={loadPosts}>
              다시 시도
            </Button>
          </div>
        ) : posts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-12 text-center">
            <p className="text-base font-semibold text-slate-700">
              아직 게시글이 없습니다.
            </p>
            <p className="mt-1 text-sm text-slate-500">
              첫 글을 작성해 이 종목의 이야기를 시작해보세요.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {posts.map((post) => (
              <CommunityPostCard key={post.postId} post={post} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
