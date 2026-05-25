package com.realityrag.access.trace;

import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class DefaultQueryIdentityGenerator implements QueryIdentityGenerator {
    @Override
    public QueryIdentity next() {
        return new QueryIdentity(
            "qry_" + UUID.randomUUID(),
            "trc_" + UUID.randomUUID()
        );
    }
}
