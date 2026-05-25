import { Input } from "../../ui/input";
import { Button } from "../../ui/button";

interface CommunityPostFormProps {
  title: string;
  content: string;
  submitting: boolean;
  submitLabel: string;
  onTitleChange: (value: string) => void;
  onContentChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

export function CommunityPostForm({
  title,
  content,
  submitting,
  submitLabel,
  onTitleChange,
  onContentChange,
  onSubmit,
  onCancel,
}: CommunityPostFormProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 md:p-6">
      <div className="space-y-4">
        <div>
          <label className="mb-2 block text-sm font-semibold text-slate-700">
            제목
          </label>
          <Input
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
            placeholder="제목을 입력하세요"
            maxLength={200}
          />
        </div>

        <div>
          <label className="mb-2 block text-sm font-semibold text-slate-700">
            내용
          </label>
          <textarea
            value={content}
            onChange={(event) => onContentChange(event.target.value)}
            placeholder="종목에 대한 의견을 작성하세요"
            className="min-h-[320px] w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-3 text-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
          />
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          취소
        </Button>
        <Button
          onClick={onSubmit}
          disabled={submitting}
          className="bg-[#155dfc] hover:bg-[#124bc9]"
        >
          {submitLabel}
        </Button>
      </div>
    </section>
  );
}
