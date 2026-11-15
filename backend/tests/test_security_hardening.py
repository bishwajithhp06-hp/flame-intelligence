import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from app.routes import ai as ai_route
from app.routes import mission as mission_route
from app.schemas.ai import QueryRequest
from app.schemas.mission import MissionAnalysisRequest
from app.services.gemini_service import GeminiResearchService


class ProductionErrorHandlingTests(unittest.TestCase):
    def test_mission_error_response_hides_internal_error_text_in_production(self):
        request = MissionAnalysisRequest.model_validate({
            "parameters": {
                "environment": "Lunar Habitat",
                "oxygen_percent": 30,
                "pressure_atm": 0.8,
                "airflow_cm_s": 15,
                "gravity": "lunar",
                "material": "pmma",
            },
            "question": "Review the hypothetical scenario.",
        })
        private_detail = "Provider error at C:\\private\\service-path"

        async def invoke():
            with patch.object(mission_route.settings, "ENVIRONMENT", "production"):
                with patch.object(
                    mission_route.mission_service,
                    "analyze",
                    new=AsyncMock(side_effect=RuntimeError(private_detail)),
                ):
                    with self.assertLogs("flame_intelligence.mission_route", level="WARNING") as captured:
                        with self.assertRaises(HTTPException) as raised:
                            await mission_route.analyze_mission(request, db=object())
            self.assertEqual(raised.exception.status_code, 503)
            self.assertEqual(raised.exception.detail, "Mission analysis is temporarily unavailable.")
            self.assertNotIn(private_detail, "\n".join(captured.output))
            self.assertIn("error_type=RuntimeError", "\n".join(captured.output))

        asyncio.run(invoke())

    def test_ai_error_response_hides_internal_error_text_in_production(self):
        request = QueryRequest(question="Review the retrieved research.")
        private_detail = "Provider error at C:\\private\\service-path"

        async def invoke():
            with patch.object(ai_route.settings, "ENVIRONMENT", "production"):
                with patch.object(
                    ai_route.ai_service,
                    "answer_question",
                    new=AsyncMock(side_effect=RuntimeError(private_detail)),
                ):
                    with self.assertLogs("flame_intelligence.ai_route", level="WARNING") as captured:
                        with self.assertRaises(HTTPException) as raised:
                            await ai_route.ask_research_assistant(request, db=object())
            self.assertEqual(raised.exception.status_code, 503)
            self.assertEqual(raised.exception.detail, "AI research analysis is temporarily unavailable.")
            self.assertNotIn(private_detail, "\n".join(captured.output))
            self.assertIn("error_type=RuntimeError", "\n".join(captured.output))

        asyncio.run(invoke())

    def test_gemini_provider_failure_log_omits_raw_exception_text(self):
        private_detail = "request included a private token-like value"
        service = GeminiResearchService()
        service.client = SimpleNamespace(models=SimpleNamespace(
            generate_content=Mock(side_effect=RuntimeError(private_detail)),
        ))
        service._retrieve_relevant_context = Mock(return_value={
            "context_text": "A retrieved research record is available.",
            "citations": [],
            "referenced_acronyms": [],
        })

        with self.assertLogs("flame_intelligence.ai", level="ERROR") as captured:
            with self.assertRaisesRegex(RuntimeError, "temporarily unavailable"):
                asyncio.run(service.answer_question(db=None, question="A test question."))
        output = "\n".join(captured.output)
        self.assertIn("error_type=RuntimeError", output)
        self.assertNotIn(private_detail, output)


if __name__ == "__main__":
    unittest.main()
