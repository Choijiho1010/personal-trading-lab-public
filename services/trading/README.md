# Trading service

Run the service from this directory so the default `../../contracts/first-demo.fixture.json` resolves to the repository fixture.

```sh
./gradlew bootRun
```

The service listens on `127.0.0.1:8080` when `SERVER_ADDRESS=127.0.0.1` is supplied by the integration entrypoint. `SERVER_PORT`, `RESEARCH_BASE_URL`, `RESEARCH_TIMEOUT_MS`, and `TRADING_FIXTURE_PATH` override the defaults. The fixture path is intentionally relative to this service working directory; use an absolute `TRADING_FIXTURE_PATH` when launching from elsewhere.

```sh
./gradlew test
```
