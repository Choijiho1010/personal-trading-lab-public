package com.personallab.trading.config;

import com.personallab.trading.domain.FillRepository;
import com.personallab.trading.domain.ResearchClient;
import com.personallab.trading.domain.TradingService;
import com.personallab.trading.infrastructure.fixture.FixtureFillRepository;
import com.personallab.trading.infrastructure.research.HttpResearchClient;
import java.net.http.HttpClient;
import java.time.Duration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.ObjectMapper;

@Configuration
@EnableConfigurationProperties(TradingProperties.class)
public class TradingConfiguration {
    @Bean
    HttpClient researchHttpClient(TradingProperties properties) {
        return HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(properties.getResearch().getTimeoutMs()))
                .build();
    }

    @Bean
    FillRepository fillRepository(ObjectMapper objectMapper, TradingProperties properties) {
        return new FixtureFillRepository(objectMapper, properties.getFixturePath());
    }

    @Bean
    ResearchClient researchClient(HttpClient httpClient, ObjectMapper objectMapper, TradingProperties properties) {
        return new HttpResearchClient(httpClient, objectMapper, properties.getResearch().getBaseUrl(), properties.getResearch().getTimeoutMs());
    }

    @Bean
    TradingService tradingService(FillRepository fills, ResearchClient research) {
        return new TradingService(fills, research);
    }
}
