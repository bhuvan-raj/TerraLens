"""
tests/test_catalog.py — Tests for the AWS resource catalog from cli.py
"""
from insight_tf.catalog import AWS_RESOURCE_CATALOG, ALL_AWS_RESOURCES, _cat_id

# ── catalog structure ─────────────────────────────────────────────────────────

def test_catalog_has_categories():
    assert len(AWS_RESOURCE_CATALOG) > 0

def test_catalog_expected_categories():
    for cat in ("Compute", "Storage", "Database", "Networking", "IAM & Security"):
        assert cat in AWS_RESOURCE_CATALOG, f"Missing category: {cat}"

def test_catalog_each_category_has_resources():
    for cat, resources in AWS_RESOURCE_CATALOG.items():
        assert len(resources) > 0, f"Category '{cat}' is empty"

def test_catalog_resource_has_type_and_description():
    for cat, resources in AWS_RESOURCE_CATALOG.items():
        for r in resources:
            assert "type" in r, f"Missing 'type' in {cat}"
            assert "description" in r, f"Missing 'description' in {cat}"

def test_catalog_resource_types_are_strings():
    for cat, resources in AWS_RESOURCE_CATALOG.items():
        for r in resources:
            assert isinstance(r["type"], str) and r["type"]

def test_catalog_resource_types_start_with_provider():
    valid_prefixes = ("aws_", "azurerm_", "google_", "kubernetes_", "docker_")
    for cat, resources in AWS_RESOURCE_CATALOG.items():
        for r in resources:
            assert r["type"].startswith(valid_prefixes), (
                f"Unexpected type format: {r['type']}"
            )


# ── ALL_AWS_RESOURCES ─────────────────────────────────────────────────────────

def test_all_aws_resources_not_empty():
    assert len(ALL_AWS_RESOURCES) > 0

def test_all_aws_resources_no_duplicates():
    types = [r["type"] for r in ALL_AWS_RESOURCES]
    assert len(types) == len(set(types)), "Duplicate resource types found"

def test_all_aws_resources_has_category():
    for r in ALL_AWS_RESOURCES:
        assert "category" in r, f"Missing category on {r['type']}"

def test_all_aws_resources_category_exists_in_catalog():
    for r in ALL_AWS_RESOURCES:
        assert r["category"] in AWS_RESOURCE_CATALOG

def test_all_aws_resources_contains_common_types():
    types = {r["type"] for r in ALL_AWS_RESOURCES}
    for rtype in ("aws_instance", "aws_s3_bucket", "aws_vpc", "aws_iam_role", "aws_lambda_function"):
        assert rtype in types, f"Missing expected resource: {rtype}"


# ── _cat_id ───────────────────────────────────────────────────────────────────

def test_cat_id_basic():
    assert _cat_id("Compute") == "cat-Compute"

def test_cat_id_spaces():
    assert _cat_id("Load Balancing") == "cat-Load_Balancing"

def test_cat_id_ampersand():
    assert _cat_id("IAM & Security") == "cat-IAM_and_Security"

def test_cat_id_no_spaces_in_result():
    for cat in AWS_RESOURCE_CATALOG:
        assert " " not in _cat_id(cat)

def test_cat_id_starts_with_cat_prefix():
    for cat in AWS_RESOURCE_CATALOG:
        assert _cat_id(cat).startswith("cat-")
