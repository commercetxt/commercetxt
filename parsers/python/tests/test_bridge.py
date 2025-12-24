import pytest
from commercetxt.model import ParseResult
from commercetxt.bridge import CommerceAIBridge


@pytest.fixture
def bridge():
    """
    Setup a basic CommerceAIBridge instance with a standard ParseResult.
    Used as a baseline for most unit tests.
    """
    result = ParseResult(
        directives={
            "IDENTITY": {"Name": "Store", "Currency": "USD"},
            "PRODUCT": {"Name": "Widget"},
            "OFFER": {
                "Price": "10",
                "Availability": "InStock",
                "URL": "https://example.com/buy",
            },
        }
    )
    return CommerceAIBridge(result)


def test_low_token_prompt_generation(bridge):
    """Verify that basic product information is correctly formatted in the prompt."""
    prompt = bridge.generate_low_token_prompt()
    assert "STORE: Store" in prompt
    assert "ITEM: Widget" in prompt
    assert "URL: https://example.com/buy" in prompt


def test_readiness_score_calculation(bridge):
    """Ensure the AI readiness score reacts correctly to missing data and trust flags."""
    # Perfect score scenario
    bridge.result.version = "1.0.1"
    score_data = bridge.calculate_readiness_score()
    assert score_data["score"] == 100

    # Test penalty for stale inventory
    bridge.result.trust_flags.append("inventory_stale")
    score_data = bridge.calculate_readiness_score()
    assert score_data["score"] == 85
    assert "Stale inventory" in score_data["issues"][0]


def test_prompt_semantic_logic(bridge):
    """Check if AI_LOGIC_RULES correctly maps names and paths for the LLM."""
    bridge.result.directives["SEMANTIC_LOGIC"] = {
        "items": [{"name": "Question", "path": "Answer"}]
    }
    prompt = bridge.generate_low_token_prompt()
    assert "AI_LOGIC_RULES:" in prompt
    assert "Question -> Answer" in prompt


def test_prompt_visuals_with_alt(bridge):
    """Verify that image ALT text is extracted and presented as a description."""
    bridge.result.directives["IMAGES"] = {
        "items": [{"name": "Main", "Alt": '"Front view of phone"'}]
    }
    prompt = bridge.generate_low_token_prompt()
    assert "VISUALS:" in prompt
    assert "Main: Describes Front view of phone" in prompt


def test_prompt_age_restriction(bridge):
    """Legal check: Ensure safety/age restrictions are clearly flagged."""
    bridge.result.directives["AGE_RESTRICTION"] = {"MinimumAge": "18"}
    prompt = bridge.generate_low_token_prompt()
    assert "SAFETY: Restricted to ages 18+" in prompt


# --- NEW TESTS FOR VERSION 1.0.2 ---


def test_prompt_promos(bridge):
    """Test if active promotions are correctly included in the prompt."""
    bridge.result.directives["PROMOS"] = {
        "items": [{"name": "SALE20", "value": "20% off with code"}]
    }
    prompt = bridge.generate_low_token_prompt()
    assert "PROMOS:" in prompt
    assert "- SALE20: 20% off with code" in prompt


def test_prompt_brand_voice(bridge):
    """Ensure that brand personality guidelines are passed to the AI."""
    bridge.result.directives["BRAND_VOICE"] = {
        "Tone": "Helpful",
        "Guidelines": "Be concise and polite.",
    }
    prompt = bridge.generate_low_token_prompt()
    assert "TONE_OF_VOICE: Helpful" in prompt
    assert "VOICE_GUIDELINES: Be concise and polite." in prompt


def test_token_limit_handling(bridge):
    """
    Security/Optimization check: Ensure bridge doesn't overflow tokens
    by limiting the number of specs or variants shown.
    """
    # Create 10 specs, bridge should only show 5
    many_specs = {f"Spec{i}": "Value" for i in range(10)}
    bridge.result.directives["SPECS"] = many_specs

    prompt = bridge.generate_low_token_prompt()
    assert "Spec0: Value" in prompt
    assert "Spec4: Value" in prompt
    assert "Spec6: Value" not in prompt


def test_full_spectrum_prompt_coverage(bridge):
    """
    Execute a test with all optional directives to maximize coverage of bridge.py.
    This hits the 'Shipping', 'Voice', 'Safety', and 'Inventory' branches.
    """
    bridge.result.directives.update(
        {
            "INVENTORY": {"Stock": 100, "LastUpdated": "2025-12-20"},
            "REVIEWS": {"Rating": "5", "Count": "10", "TopTags": "Excellent"},
            "SPECS": {"Color": "Red", "Size": "XL", "Material": "Cotton"},
            "VARIANTS": {
                "Type": "Size",
                "Options": [
                    {"name": "S"},
                    {"name": "M"},
                    {"name": "L"},
                    {"name": "XL"},
                ],
            },
            "SHIPPING": {"items": [{"name": "Express", "path": "Next Day"}]},
            "BRAND_VOICE": {"Tone": "Formal", "Guidelines": "Polite"},
            "AGE_RESTRICTION": {"MinimumAge": "21"},
        }
    )
    bridge.result.trust_flags.append("inventory_stale")

    prompt = bridge.generate_low_token_prompt()

    # Assertions to ensure branches were entered
    assert "STOCK: 100 units" in prompt
    assert "SHIPPING:" in prompt
    assert "TONE_OF_VOICE: Formal" in prompt
    assert "SAFETY: Restricted to ages 21+" in prompt
    assert "NOTE: Inventory data may be outdated" in prompt


def test_maximum_coverage_bridge(bridge):
    # """
    # Execute a test that maximizes code coverage in bridge.py by including all possible directives
    # and error conditions.
    # This test ensures that every branch and condition in the bridge logic is exercised.
    # """

    bridge.result.directives.update(
        {
            "IDENTITY": {},
            "PRODUCT": {"Name": None},
            "BRAND_VOICE": {"Tone": "Formal", "Guidelines": "Strictly professional"},
            "SHIPPING": {"items": [{"name": "Standard"}]},
            "AGE_RESTRICTION": {"MinimumAge": "18"},
        }
    )
    bridge.result.errors = ["Error 1", "Error 2", "Error 3"]

    bridge.calculate_readiness_score()
    bridge.generate_low_token_prompt()
