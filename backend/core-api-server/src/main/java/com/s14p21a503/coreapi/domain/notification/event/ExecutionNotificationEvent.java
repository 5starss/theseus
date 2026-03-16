package com.s14p21a503.coreapi.domain.notification.event;

import com.s14p21a503.coreapi.domain.order.dto.ExecutionEventDto;

public record ExecutionNotificationEvent(Long userId, ExecutionEventDto payload) {}
