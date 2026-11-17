package com.personallab.trading.domain;

import java.util.Optional;

public interface FillRepository {
    Optional<Fill> findById(String fillId);
}
