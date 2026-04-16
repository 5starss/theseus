package com.s14p21a503.coreapi.common.infra.redis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisOperations;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.SessionCallback;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Redis 메모리 데이터베이스에 접근하여 데이터를 저장하고 조회하는 공통 서비스 클래스입니다.
 * 
 * @summary Redis 공통 조작 서비스
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RedisService {

    private final RedisTemplate<String, Object> redisTemplate;
    private final ObjectMapper objectMapper;

    /**
     * 리스트 형태의 데이터를 JSON으로 직렬화하여 Redis에 저장합니다.
     * 
     * @summary 리스트 데이터 저장
     * @param <T>      리스트 요소 타입
     * @param key      저장할 키
     * @param list     저장할 리스트
     * @param duration 만료 시간
     */
    public <T> void setList(String key, List<T> list, Duration duration) {
        try {
            String value = objectMapper.writeValueAsString(list);
            redisTemplate.opsForValue().set(key, value, duration.toMillis(), TimeUnit.MILLISECONDS);
        } catch (JsonProcessingException e) {
            log.error("Redis setList error: {}", e.getMessage());
        }
    }

    public <T> List<T> getList(String key, Class<T> clazz) {
        String value = (String) redisTemplate.opsForValue().get(key);
        if (value == null)
            return null;

        try {
            return objectMapper.readValue(value,
                    objectMapper.getTypeFactory().constructCollectionType(List.class, clazz));
        } catch (JsonProcessingException e) {
            log.error("Redis getList error: {}", e.getMessage());
            return null;
        }
    }

    public void setDataWithExpiration(String key, String value, long timeout) {
        redisTemplate.opsForValue().set(key, value, timeout, TimeUnit.MILLISECONDS);
    }

    public String getData(String key) {
        return (String) redisTemplate.opsForValue().get(key);
    }

    public void deleteData(String key) {
        redisTemplate.delete(key);
    }

    public boolean hasKey(String key) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(key));
    }

    public Long increment(String key) {
        return redisTemplate.opsForValue().increment(key);
    }

    public void addToSet(String key, String value) {
        redisTemplate.opsForSet().add(key, value);
    }

    public Set<Object> getSetMembers(String key) {
        return redisTemplate.opsForSet().members(key);
    }

    public void removeFromSet(String key, String value) {
        redisTemplate.opsForSet().remove(key, value);
    }

    public String getHashField(String key, String field) {
        Object value = redisTemplate.opsForHash().get(key, field);
        return value != null ? value.toString() : null;
    }

    // 여러 Hash 키에서 동일한 필드를 Pipeline으로 일괄 조회
    // 반환: key → field 값 (없는 키는 포함되지 않음)
    public Map<String, String> getHashFieldBulk(List<String> keys, String field) {
        List<Object> results = redisTemplate.executePipelined(new SessionCallback<>() {
            @Override
            public Object execute(RedisOperations operations) {
                for (String key : keys) {
                    operations.opsForHash().get(key, field);
                }
                return null;
            }
        });

        Map<String, String> resultMap = new HashMap<>();
        for (int i = 0; i < keys.size(); i++) {
            Object value = results.get(i);
            if (value != null) {
                resultMap.put(keys.get(i), value.toString());
            }
        }
        return resultMap;
    }
}