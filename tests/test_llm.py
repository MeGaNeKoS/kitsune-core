import json
import pytest

from core.features import is_available


@pytest.mark.skipif(not is_available("llm"), reason="llm not installed")
class TestLLMFactory:

    def test_get_openai_client(self):
        from core.llm import get_llm_client
        client = get_llm_client("openai", base_url="http://localhost:1234/v1", api_key="test", model="llama3")
        assert client.get_name() == "openai"
        assert client._model == "llama3"

    def test_get_gemini_client(self):
        from core.llm import get_llm_client
        client = get_llm_client("gemini", api_key="test")
        assert client.get_name() == "gemini"
        assert "googleapis" in client._base_url

    def test_get_openrouter_client(self):
        from core.llm import get_llm_client
        client = get_llm_client("openrouter", api_key="test")
        assert client.get_name() == "openrouter"
        assert "openrouter" in client._base_url

    def test_unknown_client_raises(self):
        from core.llm import get_llm_client
        with pytest.raises(ValueError, match="not found"):
            get_llm_client("nonexistent")

    def test_custom_model(self):
        from core.llm import get_llm_client
        client = get_llm_client("openai", model="custom-model", api_key="test")
        assert client._model == "custom-model"


@pytest.mark.skipif(not is_available("llm"), reason="llm not installed")
class TestLLMAgent:

    def test_agent_loads(self):
        from core.llm.agent import LLMAgent, TOOL_DEFINITIONS, _build_tool_handlers
        assert len(TOOL_DEFINITIONS) == 6

    def test_tool_handlers_built(self):
        from core.llm.agent import _build_tool_handlers
        handlers = _build_tool_handlers()
        expected = {"search_anime", "get_anime_details", "parse_filename",
                    "get_file_info", "get_media_info", "list_media_files"}
        assert set(handlers.keys()) == expected

    def test_parse_filename_handler(self):
        from core.llm.agent import _build_tool_handlers
        handlers = _build_tool_handlers()
        result = json.loads(handlers["parse_filename"](
            filename="[SubsPlease] Frieren - 05 (1080p).mkv"
        ))
        assert result["anime_title"] == "Frieren"
        assert result["episode_number"] == 5

    def test_get_file_info_handler(self):
        from core.llm.agent import _build_tool_handlers
        handlers = _build_tool_handlers()
        result = json.loads(handlers["get_file_info"](path="pyproject.toml"))
        assert result["exists"] is True
        assert result["extension"] == "toml"

    def test_list_media_files_handler(self, tmp_path):
        from core.llm.agent import _build_tool_handlers
        (tmp_path / "video.mkv").write_text("fake")
        handlers = _build_tool_handlers()
        result = json.loads(handlers["list_media_files"](directory=str(tmp_path)))
        assert len(result) == 1
