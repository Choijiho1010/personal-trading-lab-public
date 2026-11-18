package com.personallab.trading;

import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.net.http.HttpClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK,
        properties = "trading.research.timeout-ms=100")
class ReplayApiTest {
    private static final String REPLAY = "/api/v1/ledger/replay";
    private static final String QUESTION = """
            {"symbol":"SAMPLE","from_date":"2026-11-12","as_of":"2026-11-13","question":"몇 주인가요?"}
            """;

    @Autowired
    private WebApplicationContext context;

    @MockitoBean
    private HttpClient http;

    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.webAppContextSetup(context).build();
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "?symbol=sample&from_date=2026-11-12&as_of=2026-11-13",
            "?symbol=SAMPLE&from_date=2026-02-30&as_of=2026-11-13",
            "?symbol=SAMPLE&from_date=2026-11-14&as_of=2026-11-13",
            "?symbol=SAMPLE&as_of=2026-11-13"
    })
    void rejectsInvalidReadScopes(String query) throws Exception {
        mvc.perform(get(java.net.URI.create(REPLAY + query)))
                .andExpect(status().isBadRequest())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
    }

    @Test
    void rejectsExtraQuestionFieldsBeforeAccessingLedgerOrResearch() throws Exception {
        mvc.perform(post(REPLAY + "/questions").contentType("application/json")
                        .content(QUESTION.replace("{", "{\"account_number\":\"test\",")))
                .andExpect(status().isBadRequest())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
        verifyNoInteractions(http);
    }

    @Test
    void returnsLedgerUnavailableWhenReplayLedgerIsDisabled() throws Exception {
        mvc.perform(post(REPLAY + "/questions").contentType("application/json").content(QUESTION))
                .andExpect(status().isServiceUnavailable())
                .andExpect(header().exists("X-Request-ID"))
                .andExpect(jsonPath("$.code").value("LEDGER_UNAVAILABLE"));
        verifyNoInteractions(http);
    }
}
