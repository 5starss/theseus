package com.s14p21a503.coreapi.domain.user.repository;

import com.s14p21a503.coreapi.domain.user.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {

    // 이메일로 사용자 찾기 (로그인 시 필요)
    Optional<User> findByEmail(String email);

    // 이메일 중복 여부 확인
    boolean existsByEmail(String email);
}