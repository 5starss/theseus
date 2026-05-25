import { useState } from "react";
import { format } from "date-fns";
import { MessageSquare, Pencil, Trash2, Heart } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "../../../api/client";
import { communityApi } from "../../../api/community";
import type { CommunityComment } from "../../../types/community";
import { useAuthStore } from "../../../store/useAuthStore";
import { getErrorMessage } from "../../../utils/errorMessages";
import { Button } from "../../ui/button";
import { CommunityBadge } from "./CommunityBadge";

interface CommunityCommentSectionProps {
  postId: number;
  comments: CommunityComment[];
  onCommentsChange: (comments: CommunityComment[]) => void;
}

export function CommunityCommentSection({
  postId,
  comments,
  onCommentsChange,
}: CommunityCommentSectionProps) {
  const navigate = useNavigate();
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const currentUserId = useAuthStore((state) => state.user?.id);
  const [newComment, setNewComment] = useState("");
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [likeSubmittingId, setLikeSubmittingId] = useState<number | null>(null);

  const getApiMessage = (error: unknown, fallback: string) => {
    if (error instanceof ApiError) {
      return getErrorMessage(error.code, error.message);
    }
    return fallback;
  };

  const handleCreateComment = async () => {
    if (!newComment.trim()) {
      toast.error("댓글 내용을 입력해주세요.");
      return;
    }

    try {
      setSubmitting(true);
      const created = await communityApi.createComment(postId, {
        content: newComment.trim(),
      });
      onCommentsChange([...comments, created]);
      setNewComment("");
      toast.success("댓글을 작성했습니다.");
    } catch (error) {
      toast.error(getApiMessage(error, "댓글 작성에 실패했습니다."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateComment = async (commentId: number) => {
    if (!editingContent.trim()) {
      toast.error("댓글 내용을 입력해주세요.");
      return;
    }

    try {
      setSubmitting(true);
      const updated = await communityApi.updateComment(commentId, {
        content: editingContent.trim(),
      });
      onCommentsChange(
        comments.map((comment) =>
          comment.commentId === commentId ? updated : comment
        )
      );
      setEditingCommentId(null);
      setEditingContent("");
      toast.success("댓글을 수정했습니다.");
    } catch (error) {
      toast.error(getApiMessage(error, "댓글 수정에 실패했습니다."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteComment = async (commentId: number) => {
    if (!window.confirm("댓글을 삭제하시겠습니까?")) {
      return;
    }

    try {
      setSubmitting(true);
      await communityApi.deleteComment(commentId);
      onCommentsChange(
        comments.filter((comment) => comment.commentId !== commentId)
      );
      toast.success("댓글을 삭제했습니다.");
    } catch (error) {
      toast.error(getApiMessage(error, "댓글 삭제에 실패했습니다."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleLike = async (commentId: number) => {
    if (!isLoggedIn) {
      toast.error("좋아요는 로그인 후 이용할 수 있습니다.");
      navigate("/login");
      return;
    }

    try {
      setLikeSubmittingId(commentId);
      const response = await communityApi.toggleCommentLike(commentId);
      onCommentsChange(
        comments.map((comment) =>
          comment.commentId === commentId
            ? {
                ...comment,
                likeCount: response.likeCount,
                likedByMe: response.liked,
              }
            : comment
        )
      );
    } catch (error) {
      toast.error(getApiMessage(error, "좋아요 처리에 실패했습니다."));
    } finally {
      setLikeSubmittingId(null);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-6">
      <div className="flex items-center gap-2">
        <MessageSquare className="size-5 text-slate-500" />
        <h2 className="text-lg font-bold text-slate-900">
          댓글 {comments.length}
        </h2>
      </div>

      <div className="mt-5">
        {isLoggedIn ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <textarea
              value={newComment}
              onChange={(event) => setNewComment(event.target.value)}
              placeholder="종목에 대한 의견을 남겨보세요."
              className="min-h-24 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
            <div className="mt-3 flex justify-end">
              <Button
                onClick={handleCreateComment}
                disabled={submitting}
                className="bg-[#155dfc] hover:bg-[#124bc9]"
              >
                댓글 작성
              </Button>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            댓글을 작성하려면 로그인해주세요.
          </div>
        )}
      </div>

      <div className="mt-6 space-y-3">
        {comments.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            아직 댓글이 없습니다.
          </div>
        ) : (
          comments.map((comment) => {
            const isMine = currentUserId === comment.authorId;
            const isEditing = editingCommentId === comment.commentId;

            return (
              <div
                key={comment.commentId}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
                      <span className="font-semibold text-slate-900">
                        {comment.authorNickname}
                      </span>
                      <CommunityBadge isShareholder={comment.isShareholder} />
                      <span className="text-slate-300">|</span>
                      <span>
                        {format(new Date(comment.createdAt), "yyyy.MM.dd HH:mm")}
                      </span>
                    </div>

                    {isEditing ? (
                      <div className="mt-3">
                        <textarea
                          value={editingContent}
                          onChange={(event) => setEditingContent(event.target.value)}
                          className="min-h-24 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                        />
                        <div className="mt-3 flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setEditingCommentId(null);
                              setEditingContent("");
                            }}
                          >
                            취소
                          </Button>
                          <Button
                            size="sm"
                            disabled={submitting}
                            onClick={() => handleUpdateComment(comment.commentId)}
                            className="bg-[#155dfc] hover:bg-[#124bc9]"
                          >
                            저장
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                          {comment.content}
                        </p>
                        <div className="mt-3">
                          <button
                            type="button"
                            disabled={likeSubmittingId === comment.commentId}
                            onClick={() => handleToggleLike(comment.commentId)}
                            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold transition ${
                              comment.likedByMe
                                ? "border-rose-200 bg-rose-50 text-rose-600"
                                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                            }`}
                          >
                            <Heart
                              className={`size-3.5 ${
                                comment.likedByMe ? "fill-current" : ""
                              }`}
                            />
                            {comment.likeCount}
                          </button>
                        </div>
                      </>
                    )}
                  </div>

                  {isMine && !isEditing ? (
                    <div className="flex shrink-0 items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingCommentId(comment.commentId);
                          setEditingContent(comment.content);
                        }}
                      >
                        <Pencil className="size-4" />
                        수정
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteComment(comment.commentId)}
                      >
                        <Trash2 className="size-4" />
                        삭제
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
