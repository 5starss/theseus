package com.s14p21a503.coreapi.common.config.async;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean(name = "notificationExecutor")
    public Executor notificationExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);                            // 기본적으로 유지할 수 있는 스레드 수
        executor.setMaxPoolSize(10);                            // 최대 늘어날 수 있는 스레드 수
        executor.setQueueCapacity(500);                         // 작업 대기열 크기
        executor.setThreadNamePrefix("notification-");
        executor.setWaitForTasksToCompleteOnShutdown(true);     // 서버 종료 시 진행 중인 작업을 최대한 마치고 종료하도록 설정
        executor.setAwaitTerminationSeconds(60);
        executor.initialize();
        return executor;
    }
}
