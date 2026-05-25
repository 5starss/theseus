import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { format } from "date-fns";
import { Eye, MessageSquare, Pencil, Trash2, ChevronLeft, Heart } from "lucide-react";
import { toast } from "sonner";
import { communityApi } from "../api/community";
import { stockApi } from "../api/stock";
import { ApiError } from "../api/client";
import type { CommunityComment, CommunityPostDetail } from "../types/community";
import { useAuthStore } from "../store/useAuthStore";
import { getErrorMessage } from "../utils/errorMessages";
import { Button } from "../components/ui/button";
import { CommunityBadge } from "../components/stock/community/CommunityBadge";
import { CommunityCommentSection } from "../components/stock/community/CommunityCommentSection";

export default function CommunityPostDetailPage() {
  const navigate = useNavigate();
  const { code, postId } = useParams<{ code: string; postId: string }>();
  const currentUserId = useAuthStore((state) => state.user?.id);
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const [post, setPost] = useState<CommunityPostDetail | null>(null);
  const [comments, setComments] = useState<CommunityComment[]>([]);
  const [stockName, setStockName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [likeSubmitting, setLikeSubmitting] = useState(false);

  const numericPostId = Number(postId);

  const getApiMessage = (error: unknown, fallback: string) => {
    if (error instanceof ApiError) {
      return getErrorMessage(error.code, error.message);
    }
    return fallback;
  };

  useEffect(() => {
    const loadPage = async () => {
      if (!code || !numericPostId) {
        setError("잘못된 게시글 경로입니다.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        await communityApi.increasePostViewCount(numericPostId);
        const [postDetail, commentList, stockSnapshot] = await Promise.all([
          communityApi.getPostDetail(numericPostId),
          communityApi.getComments(numericPostId),
          stockApi.getTickSnapshot(code),
        ]);

        setPost(postDetail);
        setComments(commentList);
        setStockName(stockSnapshot?.name || postDetail.stockName || code);
      } catch (error) {
        setError(getApiMessage(error, "게시글을 불러오지 못했습니다."));
      } finally {
        setLoading(false);
      }
    };

    loadPage();
  }, [code, numericPostId]);

  const isMine = useMemo(
    () => !!post && currentUserId === post.authorId,
    [currentUserId, post]
  );

  const handleDeletePost = async () => {
    if (!post || !window.confirm("게시글을 삭제하시겠습니까?")) {
      return;
    }

    try {
      await communityApi.deletePost(post.postId);
      toast.success("게시글을 삭제했습니다.");
      navigate(`/stock/${code}`);
    } catch (error) {
      toast.error(getApiMessage(error, "게시글 삭제에 실패했습니다."));
    }
  };

  const handleToggleLike = async () => {
    if (!post) {
      return;
    }

    if (!isLoggedIn) {
      toast.error("좋아요는 로그인 후 이용할 수 있습니다.");
      navigate("/login");
      return;
    }

    try {
      setLikeSubmitting(true);
      const response = await communityApi.togglePostLike(post.postId);
      setPost((current) =>
        current
          ? {
              ...current,
              likeCount: response.likeCount,
              likedByMe: response.liked,
            }
          : current
      );
    } catch (error) {
      toast.error(getApiMessage(error, "좋아요 처리에 실패했습니다."));
    } finally {
      setLikeSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="w-full p-4 md:p-6">
        <div className="mx-auto max-w-4xl space-y-4">
          <div className="h-10 animate-pulse rounded-xl bg-slate-200" />
          <div className="h-64 animate-pulse rounded-2xl bg-slate-200" />
          <div className="h-48 animate-pulse rounded-2xl bg-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="w-full p-4 md:p-6">
        <div className="mx-auto max-w-4xl rounded-2xl border border-red-100 bg-red-50 p-8 text-center">
          <p className="text-sm font-medium text-red-700">
            {error || "게시글을 찾을 수 없습니다."}
          </p>
          <Button asChild variant="outline" className="mt-4">
            <Link to={`/stock/${code}`}>종목 화면으로 돌아가기</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full p-4 md:p-6">
      <div className="mx-auto max-w-4xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button asChild variant="ghost" className="px-0 text-slate-600">
            <Link to={`/stock/${code}`}>
              <ChevronLeft className="size-4" />
              {stockName} 커뮤니티로 돌아가기
            </Link>
          </Button>

          {isMine ? (
            <div className="flex items-center gap-2">
              <Button asChild size="sm" variant="outline">
                <Link to={`/stock/${code}/community/posts/${post.postId}/edit`}>
                  <Pencil className="size-4" />
                  수정
                </Link>
              </Button>
              <Button size="sm" variant="outline" onClick={handleDeletePost}>
                <Trash2 className="size-4" />
                삭제
              </Button>
            </div>
          ) : null}
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-6">
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
            <span className="rounded-full bg-blue-50 px-2.5 py-1 font-semibold text-blue-700">
              {stockName}
            </span>
            <span>{post.stockCode}</span>
          </div>

          <h1 className="mt-4 text-2xl font-bold leading-tight text-slate-900">
            {post.title}
          </h1>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span className="font-semibold text-slate-900">{post.authorNickname}</span>
            <CommunityBadge isShareholder={post.isShareholder} />
            <span className="text-slate-300">|</span>
            <span>{format(new Date(post.createdAt), "yyyy.MM.dd HH:mm")}</span>
            <span className="text-slate-300">|</span>
            <span className="inline-flex items-center gap-1">
              <Eye className="size-4" />
              {post.viewCount}
            </span>
            <span className="inline-flex items-center gap-1">
              <MessageSquare className="size-4" />
              {comments.length}
            </span>
            <button
              type="button"
              onClick={handleToggleLike}
              disabled={likeSubmitting}
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold transition ${
                post.likedByMe
                  ? "border-rose-200 bg-rose-50 text-rose-600"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              <Heart className={`size-4 ${post.likedByMe ? "fill-current" : ""}`} />
              {post.likeCount}
            </button>
          </div>

          <div className="mt-6 rounded-2xl bg-slate-50 p-4">
            <p className="whitespace-pre-wrap text-[15px] leading-7 text-slate-800">
              {post.content}
            </p>
          </div>
        </section>

        <CommunityCommentSection
          postId={post.postId}
          comments={comments}
          onCommentsChange={(nextComments) => {
            setComments(nextComments);
            setPost((current) =>
              current
                ? {
                    ...current,
                    commentCount: nextComments.length,
                  }
                : current
            );
          }}
        />
      </div>
    </div>
  );
}
