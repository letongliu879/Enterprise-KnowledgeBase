package com.realityrag.access.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
public class HttpClientConfig {
    @Bean
    RestClient retrievalRestClient(RestClient.Builder builder, AccessProperties properties) {
        var requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout((int) properties.getRetrieval().getConnectTimeout().toMillis());
        requestFactory.setReadTimeout((int) properties.getRetrieval().getReadTimeout().toMillis());
        return builder
            .baseUrl(properties.getRetrieval().getBaseUrl())
            .requestFactory(requestFactory)
            .build();
    }
}
