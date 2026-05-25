export interface CommunityPageResponse<T> {
  content: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
  last: boolean;
}

export interface CommunityPostListItem {
  postId: number;
  stockCode: string;
  stockName: string;
  title: string;
  authorId: number;
  authorNickname: string;
  createdAt: string;
  updatedAt: string;
  viewCount: number;
  commentCount: number;
  isShareholder: boolean;
}

export interface CommunityPostDetail {
  postId: number;
  stockCode: string;
  stockName: string;
  title: string;
  content: string;
  authorId: number;
  authorNickname: string;
  createdAt: string;
  updatedAt: string;
  viewCount: number;
  commentCount: number;
  isShareholder: boolean;
}

export interface CommunityComment {
  commentId: number;
  postId: number;
  authorId: number;
  authorNickname: string;
  content: string;
  createdAt: string;
  updatedAt: string;
  isShareholder: boolean;
}

export interface CommunityPostCreateRequest {
  stockId?: string;
  stockCode?: string;
  title: string;
  content: string;
}

export interface CommunityPostUpdateRequest {
  title: string;
  content: string;
}

export interface CommunityCommentCreateRequest {
  content: string;
}

export interface CommunityCommentUpdateRequest {
  content: string;
}
