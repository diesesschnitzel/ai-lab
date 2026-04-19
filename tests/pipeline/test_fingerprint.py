"""Tests for URL fingerprinting module."""


from src.apivault.pipeline.fingerprint import (
    canonicalize_domain,
    extract_base_url,
    extract_docs_url,
    fingerprint_domain,
    fingerprint_url,
    get_domain_path_prefix,
    normalize_url,
)


class TestNormalizeUrl:
    def test_lowercase_scheme_and_host(self):
        assert normalize_url("HTTPS://API.Example.COM/path") == "https://api.example.com/path"

    def test_remove_trailing_slash(self):
        assert normalize_url("https://api.example.com/path/") == "https://api.example.com/path"

    def test_keep_root_slash(self):
        assert normalize_url("https://api.example.com/") == "https://api.example.com/"

    def test_remove_www_prefix(self):
        assert normalize_url("https://www.example.com/api") == "https://example.com/api"

    def test_remove_default_http_port(self):
        assert normalize_url("http://example.com:80/api") == "http://example.com/api"

    def test_remove_default_https_port(self):
        assert normalize_url("https://example.com:443/api") == "https://example.com/api"

    def test_keep_non_default_port(self):
        assert normalize_url("https://example.com:8080/api") == "https://example.com:8080/api"

    def test_remove_utm_params(self):
        url = "https://api.example.com/?utm_source=google&utm_campaign=test"
        assert normalize_url(url) == "https://api.example.com/"

    def test_sort_query_params(self):
        url = "https://api.example.com/?b=2&a=1"
        assert normalize_url(url) == "https://api.example.com/?a=1&b=2"

    def test_remove_fragment(self):
        assert normalize_url("https://api.example.com/path#section") == "https://api.example.com/path"

    def test_preserves_non_utm_params(self):
        url = "https://api.example.com/?version=v1&format=json"
        assert normalize_url(url) == "https://api.example.com/?format=json&version=v1"


class TestFingerprintUrl:
    def test_same_url_same_fingerprint(self):
        fp1 = fingerprint_url("https://api.example.com/v1")
        fp2 = fingerprint_url("https://api.example.com/v1")
        assert fp1 == fp2

    def test_normalized_urls_same_fingerprint(self):
        fp1 = fingerprint_url("https://API.Example.COM/v1/")
        fp2 = fingerprint_url("https://api.example.com/v1")
        assert fp1 == fp2

    def test_different_urls_different_fingerprint(self):
        fp1 = fingerprint_url("https://api.example.com/v1")
        fp2 = fingerprint_url("https://api.example.com/v2")
        assert fp1 != fp2

    def test_fingerprint_length(self):
        fp = fingerprint_url("https://api.example.com/v1")
        assert len(fp) == 16

    def test_utm_params_dont_affect_fingerprint(self):
        fp1 = fingerprint_url("https://api.example.com/v1")
        fp2 = fingerprint_url("https://api.example.com/v1?utm_source=google")
        assert fp1 == fp2


class TestCanonicalizeDomain:
    def test_lowercase(self):
        assert canonicalize_domain("API.Example.COM") == "api.example.com"

    def test_remove_www(self):
        assert canonicalize_domain("www.example.com") == "example.com"

    def test_remove_trailing_dot(self):
        assert canonicalize_domain("example.com.") == "example.com"

    def test_strip_whitespace(self):
        assert canonicalize_domain("  example.com  ") == "example.com"

    def test_combined(self):
        assert canonicalize_domain("  WWW.Example.COM.  ") == "example.com"


class TestFingerprintDomain:
    def test_same_domain_same_fingerprint(self):
        fp1 = fingerprint_domain("api.example.com")
        fp2 = fingerprint_domain("api.example.com")
        assert fp1 == fp2

    def test_canonicalized_same_fingerprint(self):
        fp1 = fingerprint_domain("www.API.Example.COM")
        fp2 = fingerprint_domain("api.example.com")
        assert fp1 == fp2

    def test_fingerprint_length(self):
        assert len(fingerprint_domain("example.com")) == 16


class TestExtractBaseUrl:
    def test_simple_url(self):
        assert extract_base_url("https://api.example.com/v1/users") == "https://api.example.com"

    def test_url_with_port(self):
        assert extract_base_url("https://api.example.com:8080/v1") == "https://api.example.com"

    def test_url_with_www(self):
        assert extract_base_url("https://www.example.com/api") == "https://example.com"

    def test_http_url(self):
        assert extract_base_url("http://api.example.com/v1") == "http://api.example.com"


class TestExtractDocsUrl:
    def test_from_raw_data(self):
        raw = {"docs_url": "https://docs.example.com"}
        assert extract_docs_url("https://api.example.com", raw) == "https://docs.example.com"

    def test_from_raw_data_alternate_key(self):
        raw = {"documentation_url": "https://docs.example.com"}
        assert extract_docs_url("https://api.example.com", raw) == "https://docs.example.com"

    def test_url_already_docs(self):
        result = extract_docs_url("https://api.example.com/docs")
        assert result is not None
        assert "/docs" in result

    def test_generates_docs_url(self):
        result = extract_docs_url("https://api.example.com/v1")
        assert result is not None
        assert result.startswith("https://api.example.com")


class TestGetDomainPathPrefix:
    def test_simple_path(self):
        domain, prefix = get_domain_path_prefix("https://api.example.com/v1/users")
        assert domain == "api.example.com"
        assert prefix == "/v1/users"

    def test_root_path(self):
        domain, prefix = get_domain_path_prefix("https://api.example.com/")
        assert domain == "api.example.com"
        assert prefix == "/"

    def test_single_segment(self):
        domain, prefix = get_domain_path_prefix("https://api.example.com/api")
        assert domain == "api.example.com"
        assert prefix == "/api"

    def test_canonicalizes_domain(self):
        domain, prefix = get_domain_path_prefix("https://www.API.Example.COM/v1")
        assert domain == "api.example.com"
