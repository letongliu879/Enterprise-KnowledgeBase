package com.realityrag.access.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

class RealSqliteApiKeyRegistrySmokeTest {
    @Test
    void readsApiKeyScopesFromLocalRuntimeSqliteDatabase() {
        Path dbPath = Path.of("..", "..", ".verify", "runtime", "indexing-real.db")
            .toAbsolutePath()
            .normalize();
        assumeTrue(Files.exists(dbPath), "local runtime sqlite database is not present");

        var dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("org.sqlite.JDBC");
        dataSource.setUrl("jdbc:sqlite:" + dbPath);

        var jdbcTemplate = new JdbcTemplate(dataSource);

        // Check if the new projection table exists; if not, skip
        Integer tableCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='api_key_projection'",
            Integer.class
        );
        assumeTrue(tableCount != null && tableCount > 0,
            "api_key_projection table not yet present in local runtime db — pending admin projection sync wiring");

        Integer keyCount = jdbcTemplate.queryForObject(
            "SELECT COUNT(*) FROM api_key_projection WHERE api_key_id = ?",
            Integer.class,
            "rr-agent-platform-dev"
        );
        assumeTrue(keyCount != null && keyCount > 0, "local api_key_projection dev key is not present");

        var registration = new ApiKeyRegistry(jdbcTemplate, new ObjectMapper())
            .resolve("rr-agent-platform-dev");

        assertNotNull(registration);
        assertEquals("kb_assistant", registration.agentTypeId());
        assertEquals(List.of("col_default"), registration.knowledgeScopes());
    }
}
