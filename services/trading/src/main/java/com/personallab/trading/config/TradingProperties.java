package com.personallab.trading.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("trading")
public class TradingProperties {
    private String fixturePath = "../../contracts/first-demo.fixture.json";
    private final Research research = new Research();
    private final Ledger ledger = new Ledger();

    public String getFixturePath() {
        return fixturePath;
    }

    public void setFixturePath(String fixturePath) {
        this.fixturePath = fixturePath;
    }

    public Research getResearch() {
        return research;
    }

    public Ledger getLedger() { return ledger; }

    public static class Ledger {
        private boolean enabled;
        private String url = "";
        private String username = "";
        private String password = "";
        public boolean isEnabled() { return enabled; }
        public void setEnabled(boolean enabled) { this.enabled = enabled; }
        public String getUrl() { return url; }
        public void setUrl(String url) { this.url = url; }
        public String getUsername() { return username; }
        public void setUsername(String username) { this.username = username; }
        public String getPassword() { return password; }
        public void setPassword(String password) { this.password = password; }
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
