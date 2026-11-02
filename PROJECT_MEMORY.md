# PH Memory project continuity

## Purpose and decisions
User requested PH Memory on 2026-11-02 for continuity across AI agents, accounts and chats, especially video editing, with GitHub delivery. User subsequently required that installed agents identify only PH Memory and receive no upstream branding/integration. PH Memory is standalone, standard-library-only and local-first. Skill slug ph-memory; display name PH Memory. No external memory engine, key, paid service or cloud sync is required. GitHub browser owner verified as kehuydietngo. Keep unrelated parent repository/media out of publication.

## Verified state
Skill, video/format references, Vietnamese installation/handoff guide, revision-checked CLI, portable ZIP transfer, fingerprint checks, and 18 behavioral tests are implemented. Independent forward-test passed Vietnamese video handoff, stale/concurrent writers and missing/changed media. Two malformed-input defects were fixed with regression tests. Local tests and skill validation passed before final branding cleanup; rerun after cleanup. Private GitHub repository created at https://github.com/kehuydietngo/ph-memory; upload still pending. HTTPS and SSH Git auth failed; authenticated browser upload is available.

## Next
Validate final standalone package, publish source through browser, verify remote contents. Remote CI and host-specific automatic discovery must not be claimed as tested without evidence. Project media/editor files require separate transfer.
