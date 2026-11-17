package com.personallab.trading.web;

import com.personallab.trading.domain.Fill;
import com.personallab.trading.domain.ResearchAnswer;
import com.personallab.trading.domain.TradingService;
import jakarta.servlet.http.HttpServletResponse;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;

@RestController
public class TradingController {
    private final TradingService trading;

    public TradingController(TradingService trading) {
        this.trading = trading;
    }

    @GetMapping("/api/v1/fills/{fillId}")
    Fill getFill(@PathVariable String fillId, HttpServletResponse response) {
        assignRequestId(response);
        return trading.findFill(fillId).orElseThrow(TradingService.FillNotFound::new);
    }

    @PostMapping("/api/v1/fills/{fillId}/questions")
    ResearchAnswer askAboutFill(@PathVariable String fillId, @RequestBody JsonNode body,
                                HttpServletResponse response) {
        String requestId = assignRequestId(response);
        String question = questionFrom(body);
        return trading.ask(requestId, fillId, question);
    }

    private String assignRequestId(HttpServletResponse response) {
        String requestId = UUID.randomUUID().toString();
        response.setHeader("X-Request-ID", requestId);
        return requestId;
    }

    private String questionFrom(JsonNode body) {
        if (!body.isObject() || body.size() != 1 || !body.path("question").isTextual()) {
            throw new InvalidRequest();
        }
        String question = body.path("question").asText();
        if (question.codePointCount(0, question.length()) > 500
                || question.codePoints().allMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c))) {
            throw new InvalidRequest();
        }
        return question;
    }
}
