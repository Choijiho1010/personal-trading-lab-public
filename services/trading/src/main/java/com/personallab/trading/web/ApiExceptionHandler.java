package com.personallab.trading.web;

import com.personallab.trading.domain.ResearchUnavailable;
import com.personallab.trading.domain.TradingService;
import jakarta.servlet.http.HttpServletResponse;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler({InvalidRequest.class, HttpMessageNotReadableException.class})
    ResponseEntity<Map<String, String>> invalidRequest(HttpServletResponse response) {
        return error(response, 400, "INVALID_REQUEST");
    }

    @ExceptionHandler(TradingService.FillNotFound.class)
    ResponseEntity<Map<String, String>> fillNotFound(HttpServletResponse response) {
        return error(response, 404, "FILL_NOT_FOUND");
    }

    @ExceptionHandler(ResearchUnavailable.class)
    ResponseEntity<Map<String, String>> researchUnavailable(
            ResearchUnavailable failure, HttpServletResponse response) {
        String requestId = requestId(response);
        log.warn("request_id={} service=trading operation=research status=503 reason={}",
                requestId, failure.reason());
        return error(response, 503, "RESEARCH_UNAVAILABLE");
    }

    private String requestId(HttpServletResponse response) {
        String requestId = response.getHeader("X-Request-ID");
        if (requestId == null) {
            requestId = UUID.randomUUID().toString();
            response.setHeader("X-Request-ID", requestId);
        }
        return requestId;
    }

    private ResponseEntity<Map<String, String>> error(HttpServletResponse response, int status, String code) {
        String requestId = requestId(response);
        if (status < 500) {
            log.info("request_id={} service=trading operation=fill_api status={} reason={}",
                    requestId, status, code);
        }
        return ResponseEntity.status(status).body(Map.of("code", code));
    }
}
