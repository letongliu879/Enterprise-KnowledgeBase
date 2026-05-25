package com.realityrag.retrieval;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class RetrievalApplication {
    public static void main(String[] args) {
        SpringApplication.run(RetrievalApplication.class, args);
    }
}
