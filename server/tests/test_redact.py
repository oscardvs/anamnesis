from anamnesis.redact import redact


def test_masks_known_key_shapes():
    assert "[REDACTED]" in redact("here is sk-ABCD1234abcd5678efgh in text")
    assert "AKIA" not in redact("AKIAIOSFODNN7EXAMPLE in env")
    assert "ghp_" not in redact("token ghp_0123456789abcdef0123456789abcdef0123")


def test_masks_private_key_block():
    blob = "-----BEGIN RSA PRIVATE KEY-----\nMIIEoatever\n-----END RSA PRIVATE KEY-----"
    out = redact(blob)
    assert "MIIEoatever" not in out
    assert "[REDACTED]" in out


def test_masks_sensitive_key_values_keeping_key_name():
    out = redact("DEEPSEEK_API_KEY=super-secret-value-123456")
    assert "super-secret-value-123456" not in out
    assert "DEEPSEEK_API_KEY" in out
    out2 = redact('"authorization": "Bearer abcdef0123456789ghij"')
    assert "abcdef0123456789ghij" not in out2
    assert "authorization" in out2


def test_leaves_ordinary_text_untouched():
    text = "We refactored cli.py and fixed the sync bug in store.py. No secrets here."
    assert redact(text) == text
