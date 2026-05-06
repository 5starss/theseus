package com.theseus;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@ConfigurationPropertiesScan
@SpringBootApplication
public class TheseusApiServerApplication {

	public static void main(String[] args) {
		SpringApplication.run(TheseusApiServerApplication.class, args);
	}

}
