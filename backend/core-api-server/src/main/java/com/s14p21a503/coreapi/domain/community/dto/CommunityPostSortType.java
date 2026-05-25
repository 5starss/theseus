package com.s14p21a503.coreapi.domain.community.dto;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Arrays;

@Getter
@RequiredArgsConstructor
public enum CommunityPostSortType {
    LATEST("latest"),
    LIKES("likes"),
    COMMENTS("comments"),
    VIEWS("views");

    private final String value;

    public static CommunityPostSortType from(String sort) {
        if (sort == null || sort.isBlank()) {
            return LATEST;
        }

        return Arrays.stream(values())
                .filter(type -> type.value.equalsIgnoreCase(sort.trim()))
                .findFirst()
                .orElse(LATEST);
    }
}
