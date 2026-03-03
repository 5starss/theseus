package com.s14p21a503.coreapi;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@EnableScheduling
@SpringBootApplication
public class CoreApiServerApplication {

	public static void main(String[] args) {
		SpringApplication.run(CoreApiServerApplication.class, args);
	}

}
