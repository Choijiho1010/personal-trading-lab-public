package com.personallab.trading;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.personallab.trading.domain.Fill;
import com.personallab.trading.domain.FillRepository;
import com.personallab.trading.domain.ResearchAnswer;
import com.personallab.trading.domain.ResearchClient;
import com.personallab.trading.domain.ResearchQuestion;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.MOCK,
        properties = "spring.main.allow-bean-definition-overriding=true")
class TradingApiTest {
    private static final Fill FILL = new Fill("demo-fill-1", "SAMPLE", "BUY", 4, 10000, Instant.parse("2026-11-13T00:00:00Z"), true);

    @Autowired
    private WebApplicationContext context;

    @Autowired
    private FakeResearchClient researchClient;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.webAppContextSetup(context).build();
        researchClient.answer.set(new ResearchAnswer("4주를 매수했습니다.", List.of("demo-fill-1")));
        researchClient.calls.set(0);
        researchClient.request.set(null);
        researchClient.requestId.set(null);
    }

    @Test
    void returnsTheSyntheticFill() throws Exception {
        mockMvc.perform(get("/api/v1/fills/demo-fill-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fill_id").value("demo-fill-1"))
                .andExpect(jsonPath("$.quantity").value(4))
                .andExpect(jsonPath("$.price_krw").value(10000))
                .andExpect(jsonPath("$.synthetic").value(true));
    }

    @Test
    void rejectsInvalidQuestionsWithoutCallingResearch() throws Exception {
        mockMvc.perform(post("/api/v1/fills/demo-fill-1/questions")
                        .contentType("application/json")
                        .content("{\"question\":\"   \"}"))
                .andExpect(status().isBadRequest())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

        assertThat(researchClient.calls.get()).isZero();
    }

    @Test
    void doesNotCallResearchForAnUnknownFill() throws Exception {
        mockMvc.perform(post("/api/v1/fills/missing/questions")
                        .contentType("application/json")
                        .content("{\"question\":\"몇 주야?\"}"))
                .andExpect(status().isNotFound())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.code").value("FILL_NOT_FOUND"));

        assertThat(researchClient.calls.get()).isZero();
    }

    @Test
    void sendsOnlyTheResearchAllowlistAndReturnsAValidatedAnswer() throws Exception {
        mockMvc.perform(post("/api/v1/fills/demo-fill-1/questions")
                        .contentType("application/json")
                        .content("{\"question\":\"이 거래에서 몇 주 샀어?\"}"))
                .andExpect(status().isOk())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.answer").value("4주를 매수했습니다."))
                .andExpect(jsonPath("$.evidence_ids[0]").value("demo-fill-1"));

        ResearchQuestion request = researchClient.request.get();
        assertThat(request.question()).isEqualTo("이 거래에서 몇 주 샀어?");
        assertThat(request.evidence().fillId()).isEqualTo("demo-fill-1");
        assertThat(request.evidence().quantity()).isEqualTo(4);
        assertThat(request.evidence().priceKrw()).isNull();
        assertThat(request.evidence().synthetic()).isNull();
        assertThat(UUID.fromString(researchClient.requestId.get())).isNotNull();
    }

    @Test
    void rejectsAnAnswerWithUnexpectedEvidence() throws Exception {
        researchClient.answer.set(new ResearchAnswer("4주를 매수했습니다.", List.of("other-fill")));

        mockMvc.perform(post("/api/v1/fills/demo-fill-1/questions")
                        .contentType("application/json")
                        .content("{\"question\":\"몇 주야?\"}"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("RESEARCH_UNAVAILABLE"))
                .andExpect(result -> assertThat(result.getResponse().getHeader("X-Request-ID"))
                        .isEqualTo(researchClient.requestId.get()));
    }

    @Test
    void rejectsMalformedJsonWithTheContractError() throws Exception {
        mockMvc.perform(post("/api/v1/fills/demo-fill-1/questions")
                        .contentType("application/json")
                        .content("{\"question\":"))
                .andExpect(status().isBadRequest())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
        assertThat(researchClient.calls.get()).isZero();
    }

    @Test
    void countsQuestionLengthInUnicodeCodePoints() throws Exception {
        mockMvc.perform(post("/api/v1/fills/demo-fill-1/questions")
                        .contentType("application/json")
                        .content("{\"question\":\"" + "😀".repeat(500) + "\"}"))
                .andExpect(status().isOk());
    }

    @TestConfiguration
    static class TestConfig {
        @Bean
        @Primary
        FillRepository fillRepository() {
            return fillId -> Optional.of(FILL).filter(fill -> fill.fillId().equals(fillId));
        }

        @Bean
        @Primary
        FakeResearchClient researchClient() {
            return new FakeResearchClient();
        }
    }

    static class FakeResearchClient implements ResearchClient {
        private final AtomicInteger calls = new AtomicInteger();
        private final AtomicReference<ResearchQuestion> request = new AtomicReference<>();
        private final AtomicReference<String> requestId = new AtomicReference<>();
        private final AtomicReference<ResearchAnswer> answer = new AtomicReference<>();

        @Override
        public ResearchAnswer ask(String requestId, ResearchQuestion question) {
            calls.incrementAndGet();
            this.requestId.set(requestId);
            request.set(question);
            return answer.get();
        }
    }
}
