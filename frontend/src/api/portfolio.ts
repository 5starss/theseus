import api, { type ApiResponse } from "./client";
import type { PortfolioSummaryResponse } from "../types/portfolio";

export const portfolioApi = {
    getMySummary: async (): Promise<PortfolioSummaryResponse> => {
        const response = await api.get<ApiResponse<PortfolioSummaryResponse>>(
            "/api/v1/core/portfolio/me/summary"
        );

        if (!response.data.isSuccess || !response.data.result) {
            throw new Error(response.data.message || "포트폴리오 요약 조회에 실패했습니다.");
        }

        return response.data.result;
    },
};
