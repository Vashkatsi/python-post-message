# Lessons

## respx with httpx2

respx imports `httpx` and registers a pytest plugin that loads before `conftest.py`.
`httpx2.alias_httpx()` must run before the first `import httpx`, so the plugin has to be
disabled with `-p no:respx` and the alias called at the top of `tests/conftest.py`.
Use the `@respx.mock` decorator instead of the `respx_mock` fixture.
