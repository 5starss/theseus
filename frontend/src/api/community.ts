import api, { ApiError, type ApiResponse } from "./client";
import type {
  CommunityComment,
  CommunityCommentCreateRequest,
  CommunityLikeToggleResponse,
  CommunityCommentUpdateRequest,
  CommunityPageResponse,
  CommunityPostCreateRequest,
  CommunityPostDetail,
  CommunityPostListItem,
  CommunityPostUpdateRequest,
} from "../types/community";

const BASE_URL = "/api/v1/core/community";

export const communityApi = {
  getPosts: async (
    stockCode: string,
    page = 0,
    size = 20
  ): Promise<CommunityPageResponse<CommunityPostListItem>> => {
    const response = await api.get<ApiResponse<CommunityPageResponse<CommunityPostListItem>>>(
      `${BASE_URL}/posts`,
      {
        params: { stockCode, page, size },
      }
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  getPostDetail: async (postId: number): Promise<CommunityPostDetail> => {
    const response = await api.get<ApiResponse<CommunityPostDetail>>(
      `${BASE_URL}/posts/${postId}`
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  createPost: async (
    payload: CommunityPostCreateRequest
  ): Promise<CommunityPostDetail> => {
    const response = await api.post<ApiResponse<CommunityPostDetail>>(
      `${BASE_URL}/posts`,
      payload
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  updatePost: async (
    postId: number,
    payload: CommunityPostUpdateRequest
  ): Promise<CommunityPostDetail> => {
    const response = await api.put<ApiResponse<CommunityPostDetail>>(
      `${BASE_URL}/posts/${postId}`,
      payload
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  deletePost: async (postId: number): Promise<void> => {
    await api.delete<ApiResponse<void>>(`${BASE_URL}/posts/${postId}`);
  },

  increasePostViewCount: async (postId: number): Promise<void> => {
    await api.post<ApiResponse<void>>(`${BASE_URL}/posts/${postId}/views`);
  },

  getComments: async (postId: number): Promise<CommunityComment[]> => {
    const response = await api.get<ApiResponse<CommunityComment[]>>(
      `${BASE_URL}/posts/${postId}/comments`
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  createComment: async (
    postId: number,
    payload: CommunityCommentCreateRequest
  ): Promise<CommunityComment> => {
    const response = await api.post<ApiResponse<CommunityComment>>(
      `${BASE_URL}/posts/${postId}/comments`,
      payload
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  updateComment: async (
    commentId: number,
    payload: CommunityCommentUpdateRequest
  ): Promise<CommunityComment> => {
    const response = await api.put<ApiResponse<CommunityComment>>(
      `${BASE_URL}/comments/${commentId}`,
      payload
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  deleteComment: async (commentId: number): Promise<void> => {
    await api.delete<ApiResponse<void>>(`${BASE_URL}/comments/${commentId}`);
  },

  togglePostLike: async (
    postId: number
  ): Promise<CommunityLikeToggleResponse> => {
    const response = await api.post<ApiResponse<CommunityLikeToggleResponse>>(
      `${BASE_URL}/posts/${postId}/likes`
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },

  toggleCommentLike: async (
    commentId: number
  ): Promise<CommunityLikeToggleResponse> => {
    const response = await api.post<ApiResponse<CommunityLikeToggleResponse>>(
      `${BASE_URL}/comments/${commentId}/likes`
    );

    if (!response.data.isSuccess || !response.data.result) {
      throw new ApiError(response.data.code, response.data.message);
    }

    return response.data.result;
  },
};
