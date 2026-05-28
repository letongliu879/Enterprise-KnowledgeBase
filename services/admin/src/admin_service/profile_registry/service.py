"""Profile registry service."""

from datetime import datetime, timezone

from reality_rag_contracts import ParserProfile, RetrievalProfileAdmin
from reality_rag_contracts.enums import ProfileState
from reality_rag_persistence.models import ParserProfileModel, RetrievalProfileAdminModel

from .repository import ProfileRegistryRepository
from .models import (
    ParserProfileCreateRequest,
    ParserProfileUpdateRequest,
    RetrievalProfileCreateRequest,
    RetrievalProfileUpdateRequest,
)


def _to_parser_contract(row: ParserProfileModel) -> ParserProfile:
    return ParserProfile(
        parser_profile_id=row.parser_profile_id,
        name=row.name,
        description=row.description or "",
        parser_id=row.parser_id or "naive",
        parser_config=row.parser_config or {},
        runtime_canonical_config=row.runtime_canonical_config,
        profile_hash=row.profile_hash or "",
        validator_version=row.validator_version or "",
        warnings=row.warnings or [],
        version=row.version or 1,
        state=ProfileState(row.state) if row.state else ProfileState.DRAFT,
        created_by=row.created_by or "",
        created_at=row.created_at,
        updated_by=row.updated_by or "",
        updated_at=row.updated_at,
    )


def _to_retrieval_contract(row: RetrievalProfileAdminModel) -> RetrievalProfileAdmin:
    return RetrievalProfileAdmin(
        retrieval_profile_id=row.retrieval_profile_id,
        name=row.name,
        description=row.description or "",
        profile_config=row.profile_config or {},
        runtime_canonical_config=row.runtime_canonical_config,
        profile_hash=row.profile_hash or "",
        validator_version=row.validator_version or "",
        warnings=row.warnings or [],
        version=row.version or 1,
        state=ProfileState(row.state) if row.state else ProfileState.DRAFT,
        created_by=row.created_by or "",
        created_at=row.created_at,
        updated_by=row.updated_by or "",
        updated_at=row.updated_at,
    )


class ProfilePublishError(Exception):
    """Raised when profile publish fails due to validation or downstream error."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ProfileRegistryService:
    def __init__(self, repo: ProfileRegistryRepository, actor_id: str = ""):
        self._repo = repo
        self._actor_id = actor_id

    # ── Parser Profiles ──────────────────────────────────────────────────

    def list_parser_profiles(self, state: str | None = None) -> list[ParserProfile]:
        rows = self._repo.list_parsers(state)
        return [_to_parser_contract(r) for r in rows]

    def get_parser_profile(self, parser_profile_id: str) -> ParserProfile | None:
        row = self._repo.get_parser(parser_profile_id)
        if row is None:
            return None
        return _to_parser_contract(row)

    def create_parser_profile(self, req: ParserProfileCreateRequest) -> ParserProfile:
        now = datetime.now(timezone.utc)
        profile = ParserProfileModel(
            parser_profile_id=req.parser_profile_id,
            name=req.name,
            description=req.description,
            parser_id=req.parser_id,
            parser_config=req.parser_config,
            version=1,
            state=ProfileState.DRAFT.value,
            created_by=self._actor_id,
            created_at=now,
            updated_by=self._actor_id,
            updated_at=now,
        )
        self._repo.save_parser(profile)
        return _to_parser_contract(profile)

    def update_parser_profile(self, parser_profile_id: str, req: ParserProfileUpdateRequest) -> ParserProfile | None:
        row = self._repo.get_parser(parser_profile_id)
        if row is None:
            return None
        if row.state == ProfileState.PUBLISHED.value:
            raise ValueError("Cannot modify a published profile; create a new version instead")
        if req.name is not None:
            row.name = req.name
        if req.description is not None:
            row.description = req.description
        if req.parser_config is not None:
            row.parser_config = req.parser_config
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_parser(row)
        return _to_parser_contract(row)

    def transition_parser_state(self, parser_profile_id: str, target_state: ProfileState) -> ParserProfile | None:
        row = self._repo.get_parser(parser_profile_id)
        if row is None:
            return None
        row.state = target_state.value
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_parser(row)
        return _to_parser_contract(row)

    def publish_parser_profile(
        self,
        parser_profile_id: str,
        validate_result: dict | None = None,
    ) -> ParserProfile | None:
        """Publish a draft profile. If already published, create a new version.

        If validate_result is provided, it must contain the downstream validation
        response with canonical_config, profile_hash, validator_version, and warnings.
        """
        row = self._repo.get_parser(parser_profile_id)
        if row is None:
            return None

        # Version immutability: published profiles cannot be republished in-place
        if row.state == ProfileState.PUBLISHED.value:
            # Create new version
            new_row = ParserProfileModel(
                parser_profile_id=f"{parser_profile_id}_v{(row.version or 1) + 1}",
                name=row.name,
                description=row.description or "",
                parser_id=row.parser_id or "naive",
                parser_config=row.parser_config or {},
                runtime_canonical_config=row.runtime_canonical_config,
                version=(row.version or 1) + 1,
                state=ProfileState.PUBLISHED.value,
                created_by=self._actor_id,
                created_at=datetime.now(timezone.utc),
                updated_by=self._actor_id,
                updated_at=datetime.now(timezone.utc),
            )
            # Retire old version
            row.state = ProfileState.RETIRED.value
            row.updated_by = self._actor_id
            row.updated_at = datetime.now(timezone.utc)
            self._repo.save_parser(row)
            self._repo.save_parser(new_row)
            return _to_parser_contract(new_row)

        # Apply validation result if provided
        if validate_result:
            row.runtime_canonical_config = validate_result.get("canonical_config")
            row.profile_hash = validate_result.get("profile_hash", "")
            row.validator_version = validate_result.get("validator_version", "")
            row.warnings = validate_result.get("warnings", [])

        row.state = ProfileState.PUBLISHED.value
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_parser(row)
        return _to_parser_contract(row)

    # ── Retrieval Profiles ───────────────────────────────────────────────

    def list_retrieval_profiles(self, state: str | None = None) -> list[RetrievalProfileAdmin]:
        rows = self._repo.list_retrievals(state)
        return [_to_retrieval_contract(r) for r in rows]

    def get_retrieval_profile(self, retrieval_profile_id: str) -> RetrievalProfileAdmin | None:
        row = self._repo.get_retrieval(retrieval_profile_id)
        if row is None:
            return None
        return _to_retrieval_contract(row)

    def create_retrieval_profile(self, req: RetrievalProfileCreateRequest) -> RetrievalProfileAdmin:
        now = datetime.now(timezone.utc)
        profile = RetrievalProfileAdminModel(
            retrieval_profile_id=req.retrieval_profile_id,
            name=req.name,
            description=req.description,
            profile_config=req.profile_config,
            version=1,
            state=ProfileState.DRAFT.value,
            created_by=self._actor_id,
            created_at=now,
            updated_by=self._actor_id,
            updated_at=now,
        )
        self._repo.save_retrieval(profile)
        return _to_retrieval_contract(profile)

    def update_retrieval_profile(self, retrieval_profile_id: str, req: RetrievalProfileUpdateRequest) -> RetrievalProfileAdmin | None:
        row = self._repo.get_retrieval(retrieval_profile_id)
        if row is None:
            return None
        if row.state == ProfileState.PUBLISHED.value:
            raise ValueError("Cannot modify a published profile; create a new version instead")
        if req.name is not None:
            row.name = req.name
        if req.description is not None:
            row.description = req.description
        if req.profile_config is not None:
            row.profile_config = req.profile_config
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_retrieval(row)
        return _to_retrieval_contract(row)

    def transition_retrieval_state(self, retrieval_profile_id: str, target_state: ProfileState) -> RetrievalProfileAdmin | None:
        row = self._repo.get_retrieval(retrieval_profile_id)
        if row is None:
            return None
        row.state = target_state.value
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_retrieval(row)
        return _to_retrieval_contract(row)

    def publish_retrieval_profile(
        self,
        retrieval_profile_id: str,
        validate_result: dict | None = None,
    ) -> RetrievalProfileAdmin | None:
        """Publish a draft retrieval profile. If already published, create a new version.

        If validate_result is provided, it must contain the downstream validation
        response with canonical_config, profile_hash, validator_version, and warnings.
        """
        row = self._repo.get_retrieval(retrieval_profile_id)
        if row is None:
            return None

        if row.state == ProfileState.PUBLISHED.value:
            new_row = RetrievalProfileAdminModel(
                retrieval_profile_id=f"{retrieval_profile_id}_v{(row.version or 1) + 1}",
                name=row.name,
                description=row.description or "",
                profile_config=row.profile_config or {},
                runtime_canonical_config=row.runtime_canonical_config,
                version=(row.version or 1) + 1,
                state=ProfileState.PUBLISHED.value,
                created_by=self._actor_id,
                created_at=datetime.now(timezone.utc),
                updated_by=self._actor_id,
                updated_at=datetime.now(timezone.utc),
            )
            row.state = ProfileState.RETIRED.value
            row.updated_by = self._actor_id
            row.updated_at = datetime.now(timezone.utc)
            self._repo.save_retrieval(row)
            self._repo.save_retrieval(new_row)
            return _to_retrieval_contract(new_row)

        # Apply validation result if provided
        if validate_result:
            row.runtime_canonical_config = validate_result.get("canonical_config")
            row.profile_hash = validate_result.get("profile_hash", "")
            row.validator_version = validate_result.get("validator_version", "")
            row.warnings = validate_result.get("warnings", [])

        row.state = ProfileState.PUBLISHED.value
        row.updated_by = self._actor_id
        row.updated_at = datetime.now(timezone.utc)
        self._repo.save_retrieval(row)
        return _to_retrieval_contract(row)
