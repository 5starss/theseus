package com.s14p21a503.matcher.journal;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 이벤트 페이로드와 저널 시퀀스 번호를 함께 담는 래퍼.
 */
@Getter
@RequiredArgsConstructor
public class JournaledEvent {
    private final long seqNo;
    private final Object event;
}
