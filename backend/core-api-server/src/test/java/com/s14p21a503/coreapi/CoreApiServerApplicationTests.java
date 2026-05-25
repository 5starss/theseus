package com.s14p21a503.coreapi;

import com.s14p21a503.coreapi.domain.auth.token.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest
@ActiveProfiles("test")
class CoreApiServerApplicationTests {

	@MockitoBean
	private JwtProvider jwtProvider;

	@Test
	void contextLoads() {
	}

}
