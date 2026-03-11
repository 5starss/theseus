package com.s14p21a503.coreapi.domain.user.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "users")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class User extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "user_id")
    private Long id;

    @Column(name = "email", nullable = false, length = 255, unique = true)
    private String email;

    @Column(name = "password", nullable = false, length = 255)
    private String password;

    @Column(name = "nickname", nullable = false, length = 50)
    private String nickname;

    @Column(name = "is_email_verified", nullable = false)
    private Boolean isEmailVerified = false;

    @Enumerated(EnumType.STRING)
    @Column(name = "investment_style", nullable = false)
    private InvestmentStyle investmentStyle;

    @Builder
    public User(String email,
                     String password,
                     String nickname,
                     InvestmentStyle investmentStyle) {

        this.email = email;
        this.password = password;
        this.nickname = nickname;
        this.investmentStyle = investmentStyle;
        this.isEmailVerified = false;
    }

    // 투자 성향 수정 메서드
    public void updateInvestmentStyle(InvestmentStyle investmentStyle) {
        this.investmentStyle = investmentStyle;
    }

    // 이메일 인증 메서드 (확장 예정)
    public void verifyEmail() {
        this.isEmailVerified = true;
    }

    // 닉네임 수정 메서드
    public void updateNickname(String nickname) {
        // 예: 닉네임이 비어있으면 안 된다는 규칙이 있다면?
        if (nickname == null || nickname.isBlank()) {
            throw new IllegalArgumentException("닉네임은 필수입니다.");
        }
        this.nickname = nickname;
    }

}