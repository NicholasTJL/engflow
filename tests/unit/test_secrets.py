from engflow.core.secrets import mask, secret_values


def test_secret_values_matches_common_name_suffixes() -> None:
    env = {
        "API_KEY": "abcdefgh",
        "AUTH_TOKEN": "12345678",
        "DB_SECRET": "longsecretvalue",
        "USER_PASSWORD": "hunter2hunter2",
        "PLAIN_VALUE": "not-a-secret-name",
    }

    values = secret_values(env)

    assert "abcdefgh" in values
    assert "12345678" in values
    assert "longsecretvalue" in values
    assert "hunter2hunter2" in values
    assert "not-a-secret-name" not in values


def test_secret_values_ignores_short_values() -> None:
    assert secret_values({"MY_TOKEN": "short"}) == []


def test_secret_values_is_case_insensitive_on_name() -> None:
    assert secret_values({"my_secret": "01234567"}) == ["01234567"]


def test_secret_values_skips_empty_values() -> None:
    assert secret_values({"MY_TOKEN": ""}) == []


def test_secret_values_sorted_longest_first() -> None:
    env = {"A_TOKEN": "abcdefghi", "B_TOKEN": "abcdefghijklmno"}

    values = secret_values(env)

    assert values == ["abcdefghijklmno", "abcdefghi"]


def test_mask_replaces_all_occurrences() -> None:
    text = "value=abcdefgh and again abcdefgh"

    masked = mask(text, ["abcdefgh"])

    assert "abcdefgh" not in masked
    assert masked.count("MASKED") == 2


def test_mask_longest_first_avoids_partial_shadowing() -> None:
    text = "prefix-secret-suffix"
    values = sorted(["prefix-secret-suffix", "secret"], key=len, reverse=True)

    masked = mask(text, values)

    assert "prefix-secret-suffix" not in masked
    assert "secret" not in masked


def test_mask_returns_text_unchanged_with_no_secrets() -> None:
    assert mask("nothing sensitive here", []) == "nothing sensitive here"
