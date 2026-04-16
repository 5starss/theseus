package com.s14p21a503.matcher;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class MatcherServerApplication {

	public static void main(String[] args) {
		SpringApplication.run(MatcherServerApplication.class, args);
	}

}
