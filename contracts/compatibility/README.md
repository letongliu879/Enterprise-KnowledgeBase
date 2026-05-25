# Compatibility Rules

- Additive fields must remain optional within the current major version.
- Deprecated aliases must stay readable until the next major version.
- Event payload breaking changes require a new `event_version`.
- The same semantic contract name must not drift across services.
