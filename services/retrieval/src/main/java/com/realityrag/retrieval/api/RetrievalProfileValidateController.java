package com.realityrag.retrieval.api;

import com.realityrag.retrieval.contracts.RetrievalProfileValidateRequest;
import com.realityrag.retrieval.contracts.RetrievalProfileValidateResponse;
import com.realityrag.retrieval.service.RetrievalProfileValidator;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RetrievalProfileValidateController {

    private final RetrievalProfileValidator validator;

    public RetrievalProfileValidateController(RetrievalProfileValidator validator) {
        this.validator = validator;
    }

    @PostMapping("/internal/retrieval-profiles/validate")
    public RetrievalProfileValidateResponse validate(@Valid @RequestBody RetrievalProfileValidateRequest request) {
        return validator.validate(request);
    }
}
