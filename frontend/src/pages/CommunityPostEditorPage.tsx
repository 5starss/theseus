import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { toast } from "sonner";
import { communityApi } from "../api/community";
import { stockApi } from "../api/stock";
import { ApiError } from "../api/client";
import { getErrorMessage } from "../utils/errorMessages";
import { Button } from "../components/ui/button";
import { CommunityPostForm } from "../components/stock/community/CommunityPostForm";

export default function CommunityPostEditorPage() {
  const navigate = useNavigate();
  const { code, postId } = useParams<{ code: string; postId?: string }>();
  const isEditMode = useMemo(() => !!postId, [postId]);
  const [stockName, setStockName] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(isEditMode);
  const [submitting, setSubmitting] = useState(false);

  const getApiMessage = (error: unknown, fallback: string) => {
    if (error instanceof ApiError) {
      return getErrorMessage(error.code, error.message);
    }
    return fallback;
  };

  useEffect(() => {
    const loadPage = async () => {
      if (!code) {
        return;
      }

      try {
        const stockSnapshot = await stockApi.getTickSnapshot(code);
        setStockName(stockSnapshot?.name || code);

        if (isEditMode && postId) {
          const post = await communityApi.getPostDetail(Number(postId));
          setTitle(post.title);
          setContent(post.content);
        }
      } catch (error) {
        toast.error(getApiMessage(error, "게시글 정보를 불러오지 못했습니다."));
      } finally {
        setLoading(false);
      }
    };

    loadPage();
  }, [code, isEditMode, postId]);

  const handleSubmit = async () => {
    if (!code) {
      return;
    }

    if (!title.trim() || !content.trim()) {
      toast.error("제목과 내용을 모두 입력해주세요.");
      return;
    }

    try {
      setSubmitting(true);

      if (isEditMode && postId) {
        const updated = await communityApi.updatePost(Number(postId), {
          title: title.trim(),
          content: content.trim(),
        });
        toast.success("게시글을 수정했습니다.");
        navigate(`/stock/${code}/community/posts/${updated.postId}`);
      } else {
        const created = await communityApi.createPost({
          stockCode: code,
          title: title.trim(),
          content: content.trim(),
        });
        toast.success("게시글을 작성했습니다.");
        navigate(`/stock/${code}/community/posts/${created.postId}`);
      }
    } catch (error) {
      toast.error(
        getApiMessage(
          error,
          isEditMode ? "게시글 수정에 실패했습니다." : "게시글 작성에 실패했습니다."
        )
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="w-full p-4 md:p-6">
        <div className="mx-auto max-w-4xl space-y-4">
          <div className="h-10 animate-pulse rounded-xl bg-slate-200" />
          <div className="h-[420px] animate-pulse rounded-2xl bg-slate-200" />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full p-4 md:p-6">
      <div className="mx-auto max-w-4xl space-y-4">
        <Button asChild variant="ghost" className="px-0 text-slate-600">
          <Link
            to={
              isEditMode && postId
                ? `/stock/${code}/community/posts/${postId}`
                : `/stock/${code}`
            }
          >
            <ChevronLeft className="size-4" />
            {stockName} 커뮤니티로 돌아가기
          </Link>
        </Button>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 md:p-6">
          <h1 className="text-2xl font-bold text-slate-900">
            {isEditMode ? "게시글 수정" : "게시글 작성"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {stockName || code} 커뮤니티에 의견을 남겨보세요.
          </p>
        </div>

        <CommunityPostForm
          title={title}
          content={content}
          submitting={submitting}
          submitLabel={isEditMode ? "수정 완료" : "작성 완료"}
          onTitleChange={setTitle}
          onContentChange={setContent}
          onSubmit={handleSubmit}
          onCancel={() =>
            navigate(
              isEditMode && postId
                ? `/stock/${code}/community/posts/${postId}`
                : `/stock/${code}`
            )
          }
        />
      </div>
    </div>
  );
}
