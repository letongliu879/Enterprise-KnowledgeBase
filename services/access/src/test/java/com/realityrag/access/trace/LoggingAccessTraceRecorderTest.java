package com.realityrag.access.trace;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.security.AccessRequestContext;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.TransientDataAccessResourceException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
class LoggingAccessTraceRecorderTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    private static DataSource sharedDataSource;

    private JdbcTemplate jdbcTemplate;
    private LoggingAccessTraceRecorder recorder;
    private SimpleMeterRegistry meterRegistry;

    @BeforeAll
    static void beforeAll() throws Exception {
        var config = new HikariConfig();
        config.setJdbcUrl(postgres.getJdbcUrl());
        config.setUsername(postgres.getUsername());
        config.setPassword(postgres.getPassword());
        config.setDriverClassName("org.postgresql.Driver");
        config.setMaximumPoolSize(2);
        sharedDataSource = new HikariDataSource(config);

        // Load schema.sql to create tables before any test runs
        var jdbc = new JdbcTemplate(sharedDataSource);
        try (InputStream is = LoggingAccessTraceRecorderTest.class.getClassLoader().getResourceAsStream("schema.sql")) {
            if (is != null) {
                String sql = new String(is.readAllBytes(), StandardCharsets.UTF_8);
                jdbc.execute(sql);
            }
        }
    }

    @BeforeEach
    void setUp() {
        jdbcTemplate = new JdbcTemplate(sharedDataSource);
        jdbcTemplate.update("DELETE FROM run_steps");
        jdbcTemplate.update("DELETE FROM run_traces");
        meterRegistry = new SimpleMeterRegistry();
        recorder = new LoggingAccessTraceRecorder(jdbcTemplate, new ObjectMapper(), meterRegistry);
    }

    @Test
    void writesAccessAuditEvidenceToDatabase() {
        var context = new AccessRequestContext(
            "rr-agent-platform-dev",
            "tnt_default",
            "kb_assistant",
            "agent-instance-001",
            List.of("col_default"),
            List.of("agent"),
            Map.of(),
            false,
            "rest",
            4096
        );

        recorder.recordRequestAccepted("qry_access_01", "trc_access_01", context);
        recorder.flush();
        recorder.recordResponse("qry_access_01", "trc_access_01", new KnowledgeContext(
            "qry_access_01",
            Map.of(),
            List.of("idxv_col_default_active"),
            List.of(),
            List.of(new KnowledgeContext.ResultChunk(
                "col_default",
                "doc_001",
                "chk_001",
                "dir_001",
                "text",
                List.of(),
                List.of(),
                1.0d,
                "hybrid_fusion",
                "matched"
            )),
            List.of(),
            List.of(),
            100,
            Map.of("debug_ref", "dbg://retrieval/qry_access_01")
        ));
        recorder.flush();

        Integer traceCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM run_traces WHERE run_trace_id = ? AND root_status = ? AND result_count = ?",
            Integer.class,
            "access_qry_access_01",
            "SUCCEEDED",
            1
        );
        assertThat(traceCount).isEqualTo(1);

        String details = jdbcTemplate.queryForObject(
            "SELECT details_json FROM run_steps WHERE trace_id = ? AND step_name = ?",
            String.class,
            "trc_access_01",
            "access.response"
        );
        assertThat(details)
            .contains("idxv_col_default_active")
            .contains("chk_001")
            .contains("doc_001");
    }

    @Test
    void retriesTransientFailuresAndEventuallySucceeds() {
        var failingTemplate = new FailingJdbcTemplate(sharedDataSource, 1);
        var recorderUnderTest = new LoggingAccessTraceRecorder(failingTemplate, new ObjectMapper(), meterRegistry);

        var context = new AccessRequestContext(
            "rr-agent-platform-dev",
            "tnt_default",
            "kb_assistant",
            "agent-instance-001",
            List.of("col_default"),
            List.of("agent"),
            Map.of(),
            false,
            "rest",
            4096
        );

        recorderUnderTest.recordRequestAccepted("qry_retry_01", "trc_retry_01", context);
        recorderUnderTest.flush();

        assertThat(failingTemplate.failureCount()).isGreaterThanOrEqualTo(1);
        Integer traceCount = failingTemplate.queryForObject(
            "SELECT COUNT(*) FROM run_traces WHERE run_trace_id = ? AND root_status = ?",
            Integer.class,
            "access_qry_retry_01",
            "ACCEPTED"
        );
        assertThat(traceCount).isEqualTo(1);
    }

    @Test
    void dropsAfterMaxRetriesAndIncrementsMetric() {
        var failingTemplate = new FailingJdbcTemplate(sharedDataSource, Integer.MAX_VALUE);
        var recorderUnderTest = new LoggingAccessTraceRecorder(failingTemplate, new ObjectMapper(), meterRegistry);

        var context = new AccessRequestContext(
            "rr-agent-platform-dev",
            "tnt_default",
            "kb_assistant",
            "agent-instance-001",
            List.of("col_default"),
            List.of("agent"),
            Map.of(),
            false,
            "rest",
            4096
        );

        recorderUnderTest.recordRequestAccepted("qry_drop_01", "trc_drop_01", context);
        recorderUnderTest.flush();

        assertThat(meterRegistry.counter("access.audit.dropped").count()).isEqualTo(1.0);
        assertThat(recorderUnderTest.droppedCount()).isEqualTo(1L);
    }

    private static class FailingJdbcTemplate extends JdbcTemplate {
        private final AtomicInteger remainingFailures;
        private final AtomicInteger failuresObserved = new AtomicInteger(0);

        FailingJdbcTemplate(DataSource dataSource, int remainingFailures) {
            super(dataSource);
            this.remainingFailures = new AtomicInteger(remainingFailures);
        }

        @Override
        public int update(String sql, Object... args) throws DataAccessException {
            if (remainingFailures.getAndDecrement() > 0) {
                failuresObserved.incrementAndGet();
                throw new TransientDataAccessResourceException("simulated transient failure");
            }
            return super.update(sql, args);
        }

        @Override
        public <T> List<T> query(String sql, RowMapper<T> rowMapper, Object... args) throws DataAccessException {
            if (remainingFailures.getAndDecrement() > 0) {
                failuresObserved.incrementAndGet();
                throw new TransientDataAccessResourceException("simulated transient failure");
            }
            return super.query(sql, rowMapper, args);
        }

        int failureCount() {
            return failuresObserved.get();
        }
    }
}
