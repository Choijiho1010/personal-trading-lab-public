package com.personallab.trading.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("trading")
public class TradingProperties {
    private String fixturePath = "../../contracts/first-demo.fixture.json";
    private final Research research = new Research();

    public String getFixturePath() {
        return fixturePath;
    }

    public void setFixturePath(String fixturePath) {
        this.fixturePath = fixturePath;
    }

    public Research getResearch() {
        return research;
    }

    public static class Research {
        private String baseUrl = "http://127.0.0.1:8000";
        private long timeoutMs = 1000;

        public String getBaseUrl() {
            return baseUrl;
        }

        public void setBaseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
        }

        public long getTimeoutMs() {
            return timeoutMs;
        }

        public void setTimeoutMs(long timeoutMs) {
            this.timeoutMs = timeoutMs;
        }
    }
}
