package com.personallab.trading.config;

import com.personallab.trading.domain.FillRepository;
import com.personallab.trading.domain.LedgerRepository;
import com.personallab.trading.domain.LedgerService;
import com.personallab.trading.domain.ResearchClient;
import com.personallab.trading.domain.TradingService;
import com.personallab.trading.infrastructure.fixture.FixtureFillRepository;
import com.personallab.trading.infrastructure.ledger.PostgresLedgerRepository;
import com.personallab.trading.infrastructure.research.HttpResearchClient;
import java.net.http.HttpClient;
import java.time.Duration;
import javax.sql.DataSource;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;
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

    @Bean
    @ConditionalOnProperty(prefix = "trading.ledger", name = "enabled", havingValue = "true")
    DataSource ledgerDataSource(TradingProperties properties) {
        return new DriverManagerDataSource(properties.getLedger().getUrl(), properties.getLedger().getUsername(), properties.getLedger().getPassword());
    }

    @Bean
    @ConditionalOnProperty(prefix = "trading.ledger", name = "enabled", havingValue = "true")
    LedgerRepository ledgerRepository(DataSource ledgerDataSource) {
        JdbcTemplate jdbc = new JdbcTemplate(ledgerDataSource);
        return new PostgresLedgerRepository(jdbc, new TransactionTemplate(new DataSourceTransactionManager(ledgerDataSource)));
    }

    @Bean
    @ConditionalOnProperty(prefix = "trading.ledger", name = "enabled", havingValue = "true")
    LedgerService ledgerService(LedgerRepository ledgerRepository) {
        return new LedgerService(ledgerRepository);
    }
}
