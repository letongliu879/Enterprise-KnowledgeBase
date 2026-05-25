package com.realityrag.access;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class AccessApplication {
    public static void main(String[] args) {
        SpringApplication.run(AccessApplication.class, args);
    }
}
