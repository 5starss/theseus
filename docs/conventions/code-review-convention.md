# ☑️ 코드 컨벤션

테세우스 프로젝트의 코드 작성 규칙을 정의합니다.
가독성과 일관성을 높이고, 팀원 간 이해하기 쉬운 코드를 작성하기 위해 아래 규칙을 준수합니다.

---

## 1. 축약형 사용 지양

명확한 의미 전달을 위해 축약형 사용을 지양합니다.

* 변수명, 메서드명, 클래스명은 가능한 한 의미가 드러나게 작성합니다.
* 팀원이 처음 보더라도 역할을 유추할 수 있어야 합니다.

---

## 2. 주석 작성 원칙

작성한 코드를 팀원도 이해할 수 있도록 필요한 주석을 작성합니다.

* 클래스, 메서드, 주요 로직에는 설명 가능한 수준의 주석을 남깁니다.
* 단, 코드 자체로 충분히 드러나는 내용까지 과도하게 주석 처리하지 않습니다.
* JavaDoc 스타일 주석을 우선적으로 사용합니다.

```java
/**
 * 사용자 관리를 위한 UserService 클래스
 */
public class UserService {

    /**
     * 사용자를 등록하는 메서드
     * @param user 등록할 사용자 객체
     * @return 등록된 사용자 객체
     */
    public User registerUser(User user) {
        // ...
    }
}
```

---

## 3. 패키지명 규칙

패키지 이름은 소문자로 생성하고, 역할이나 기능에 따라 명확하게 묶어서 명명합니다.

* 언더스코어 `_` 사용 금지
* 대문자 사용 금지
* 역할 중심으로 구조화

```java
com.example.project.controller
com.example.project.service
com.example.project.repository
com.example.project.model
```

---

## 4. 상수 / 변수 / 메서드 네이밍

* 상수는 **대문자 + 언더스코어(`_`)**
* 변수와 메서드는 **CamelCase**
* 의미가 드러나도록 작성

```java
// 상수
static final int MAX_COUNT = 100;

// 변수
int itemCount;

// 메서드
public String printCount() { ... }
```

---

## 5. 변수명 작명 참고

변수명을 짓기 어려울 때에는 아래 사이트를 참고합니다.

* 영어로 설정 후 원하는 단어를 검색하여 사용
* 의미 전달이 명확한 단어를 우선 선택

참고 사이트: **Curioustore**

---

## 6. Boolean 변수명 규칙

Boolean 타입의 변수는 접두사로 `is`를 사용합니다.

```java
boolean isExist;
boolean isTrue;
```

---

## 7. long 타입 표기

long 타입의 값의 마지막에는 대문자 `L`을 붙입니다.

```java
long base = 54423234211L;
```

---

## 8. 컬렉션 네이밍 규칙

컬렉션 이름은 복수형을 사용하거나 컬렉션임이 드러나도록 작성합니다.

```java
List ids;
Map<User, Integer> userMap;
```

권장 예시:

* `users`
* `userList`
* `productMap`

---

## 9. 클래스명 규칙

클래스명은 명사로 작성하고 **UpperCamelCase**를 사용합니다.

```java
private class Address { ... }
public class UserEmail { ... }
```

---

## 10. 메서드명 규칙

메서드명은 소문자로 시작하고 **동사형**으로 작성합니다.

대표적인 메서드 네이밍 규칙은 아래를 따릅니다.

```java
// 조회(상세)
getXXX()
getXXXDetail()
getXXXInfo()

// 조회(리스트)
getXXXList()

// 조회(카운트)
getXXXCount()

// 등록
createXXX()
addXXX()
registXXX()

// 수정
updateXXX()
modifyXXX()

// 삭제
removeXXX()
deleteXXX()
```

---

## 11. Enum 네이밍 규칙

Enum 변수의 이름은 대문자로 작성합니다.

```java
// 상태 - XXX_STATUS
public enum MemberStatus {
    WAITING_STATUS,    // 수락 대기 상태
    ACCEPT_STATUS,     // 수락 상태
    WITHDRAW_STATUS    // 탈퇴 상태
}

// 유형 - XXX_TYPE
public enum UserType {
    ADMIN_TYPE,
    CUSTOMER_TYPE,
    GUEST_TYPE;
}
```

---

## 12. Builder용 static 메서드 네이밍

builder를 호출하는 static 메서드는 아래 규칙을 따릅니다.

### 12-1. 파라미터가 1개인 경우: `xxxFrom`

```java
public static User createUserFromUsername(String username) {
    return new User(username);
}
```

### 12-2. 파라미터가 2개 이상인 경우: `xxxOf`

```java
public static User createUserOf(String username, String email) {
    return new User(username, email);
}
```

---

## 13. 객체 변환 메서드명 규칙

다른 객체로 변환하는 메서드의 이름은 `toEntity` 형식으로 선언합니다.

```java
@Getter
public class ProductCreateRequest {
    private ProductType type;
    private ProductSellingStatus sellingStatus;
    private String name;
    private int price;

    @Builder
    private ProductCreateRequest(ProductType type, ProductSellingStatus sellingStatus, String name, int price) {
        this.type = type;
        this.sellingStatus = sellingStatus;
        this.name = name;
        this.price = price;
    }

    public Product toEntity(String productNumber) {
        return Product.builder()
                .productNumber(productNumber)
                .type(type)
                .sellingStatus(sellingStatus)
                .name(name)
                .price(price)
                .build();
    }
}
```

---

## 14. DTO 반환 규칙

DTO에서 배열 1개만 반환할 경우에는 DTO에 담지 않고 **배열 자체를 반환**합니다.

### 지양하는 방식

```json
{
  "list": [
    "안녕하세요",
    "손석우입니다."
  ]
}
```

위와 같은 구조는 프론트엔드에서 `list`에 한 번 더 접근해야 하므로 번거로울 수 있습니다.

### 권장 방식

```json
[
  "안녕하세요",
  "손석우입니다."
]
```

즉, 단일 배열만 반환하는 경우에는 불필요한 DTO 래핑을 지양합니다.

---

## 15. 목적

본 코드 컨벤션의 목적은 다음과 같습니다.

* 코드의 일관성 유지
* 팀원 간 원활한 협업
* 가독성 향상
* 유지보수 비용 절감

---
