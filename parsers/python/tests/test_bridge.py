from commercetxt.model import ParseResult
from commercetxt.bridge import CommerceAIBridge


def test_low_token_prompt_generation():
    """Test AI prompt generation from bridge.py content."""
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

    bridge = CommerceAIBridge(result)
    prompt = bridge.generate_low_token_prompt()

    assert "STORE: Store" in prompt
    assert "CURRENCY: USD" in prompt
    assert "ITEM: Widget" in prompt
    assert "PRICE: 10" in prompt
    assert "BUY_LINK: https://example.com/buy" in prompt


def test_readiness_score_calculation():
    """Test the LLM readiness scoring logic."""
    # Scenario 1: Missing core data
    result = ParseResult(
        version="1.0.1", directives={"OFFER": {"Price": "10"}}  # Missing Availability
    )
    bridge = CommerceAIBridge(result)
    score_data = bridge.calculate_readiness_score()

    assert score_data["score"] < 100
    assert any("Missing core offer data" in issue for issue in score_data["issues"])

    result.directives["OFFER"]["Availability"] = "InStock"
    score_data = bridge.calculate_readiness_score()
    assert score_data["score"] == 100
    assert score_data["grade"] == "A"

    result.trust_flags.append("inventory_stale")
    score_data = bridge.calculate_readiness_score()
    assert score_data["score"] == 85  # 100 - 15
    assert any("Stale inventory" in issue for issue in score_data["issues"])
