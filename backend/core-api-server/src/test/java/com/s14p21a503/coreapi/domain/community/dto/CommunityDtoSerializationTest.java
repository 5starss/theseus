package com.s14p21a503.coreapi.domain.community.dto;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CommunityDtoSerializationTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void postSummarySerializesIsShareholderFieldName() throws Exception {
        CommunityPostSummaryResponseDto dto = CommunityPostSummaryResponseDto.builder()
                .postId(1L)
                .stockCode("005930")
                .title("title")
                .authorId(1L)
                .authorNickname("tester")
                .viewCount(1L)
                .commentCount(0L)
                .isShareholder(true)
                .build();

        String json = objectMapper.writeValueAsString(dto);

        assertTrue(json.contains("\"isShareholder\":true"));
        assertFalse(json.contains("\"shareholder\":true"));
    }

    @Test
    void postDetailSerializesIsShareholderFieldName() throws Exception {
        CommunityPostDetailResponseDto dto = CommunityPostDetailResponseDto.builder()
                .postId(1L)
                .stockCode("005930")
                .title("title")
                .content("content")
                .authorId(1L)
                .authorNickname("tester")
                .viewCount(1L)
                .commentCount(0L)
                .isShareholder(true)
                .build();

        String json = objectMapper.writeValueAsString(dto);

        assertTrue(json.contains("\"isShareholder\":true"));
        assertFalse(json.contains("\"shareholder\":true"));
    }

    @Test
    void commentSerializesIsShareholderFieldName() throws Exception {
        CommunityCommentResponseDto dto = CommunityCommentResponseDto.builder()
                .commentId(1L)
                .postId(1L)
                .authorId(1L)
                .authorNickname("tester")
                .content("content")
                .isShareholder(true)
                .build();

        String json = objectMapper.writeValueAsString(dto);

        assertTrue(json.contains("\"isShareholder\":true"));
        assertFalse(json.contains("\"shareholder\":true"));
    }
}
