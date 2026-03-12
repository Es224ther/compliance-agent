from tools.schema_validator import validate_parse_scenario_output


def test_schema_validator_resets_invalid_fields_to_none() -> None:
    result = validate_parse_scenario_output(
        {
            "region": "US",
            "data_types": ["Personal", "Unknown"],
            "cross_border": True,
            "third_party_model": "yes",
            "aigc_output": False,
            "data_volume_level": "Huge",
        }
    )

    assert result.parsed_fields.region is None
    assert result.parsed_fields.data_types is None
    assert result.parsed_fields.cross_border is True
    assert result.parsed_fields.third_party_model is None
    assert result.parsed_fields.aigc_output is False
    assert result.parsed_fields.data_volume_level is None
    assert result.invalid_fields == [
        "region",
        "data_types",
        "third_party_model",
        "data_volume_level",
    ]
