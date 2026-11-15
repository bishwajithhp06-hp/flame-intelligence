import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.investigation import Investigation, Publication, ResearchFinding, CombustionDataPoint
from app.schemas.ai import Citation, QueryResponse

logger = logging.getLogger("flame_intelligence.ai")

class GeminiResearchService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini Client successfully initialized with Google GenAI SDK.")
            except Exception as e:
                logger.warning(
                    "Could not initialize Google GenAI Client: error_type=%s",
                    type(e).__name__,
                )

    def _retrieve_relevant_context(self, db: Session, question: str, investigation_filter: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves grounded NASA records relevant to the query to feed into RAG prompt."""
        query = db.query(Investigation)
        if investigation_filter:
            query = query.filter(Investigation.acronym.ilike(f"%{investigation_filter}%"))
        
        all_invs = query.all()

        # Score investigations based on keyword relevance
        tokens = [t.lower() for t in question.split() if len(t) > 3]
        scored = []
        for inv in all_invs:
            score = 0
            text_corpus = f"{inv.title} {inv.acronym} {inv.description} {inv.fuel_types} {inv.key_findings} {inv.fire_safety_relevance}".lower()
            for token in tokens:
                if token in text_corpus:
                    score += 2
                if inv.acronym.lower() in token:
                    score += 5
            scored.append((score, inv))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_invs = [item[1] for item in scored[:3]] if scored else all_invs[:2]

        context_blocks = []
        citations: List[Citation] = []
        referenced_acronyms: List[str] = []

        for inv in top_invs:
            referenced_acronyms.append(inv.acronym)
            block = f"### NASA Investigation: {inv.title} ({inv.acronym})\n"
            block += f"- Facility & Mission: {inv.facility} | {inv.flight_mission}\n"
            block += f"- Principal Investigator: {inv.principal_investigator} ({inv.institution})\n"
            block += f"- Fuels & Environment: {inv.fuel_types} | {inv.oxidizer_environment}\n"
            block += f"- Description: {inv.description}\n"
            block += f"- Key Scientific Findings: {inv.key_findings}\n"
            block += f"- Fire Safety Relevance: {inv.fire_safety_relevance}\n"

            # Add primary publication
            if inv.publications:
                pub = inv.publications[0]
                block += f"- Landmark Publication: '{pub.title}', {pub.authors} ({pub.year}). DOI: {pub.doi or 'N/A'}\n"
                citations.append(Citation(
                    title=pub.title,
                    source=f"Local database publication — {inv.acronym}; provenance unverified",
                    identifier=pub.ntrs_id or inv.investigation_id,
                    doi=pub.doi,
                    url=pub.url or inv.source_url,
                    relevance_snippet=inv.key_findings[:200] + "..." if inv.key_findings else None
                ))

            # The legacy flag is not sufficient to establish flight provenance.
            if inv.datapoints:
                block += "- Local datapoints are present, but their experimental provenance is unverified and they are excluded from evidence claims.\n"

            context_blocks.append(block)

        return {
            "context_text": "\n\n".join(context_blocks),
            "citations": citations,
            "referenced_acronyms": referenced_acronyms
        }

    async def answer_question(self, db: Session, question: str, investigation_filter: Optional[str] = None) -> QueryResponse:
        retrieval = self._retrieve_relevant_context(db, question, investigation_filter)
        context_text = retrieval["context_text"]
        citations = retrieval["citations"]
        acronyms = retrieval["referenced_acronyms"]

        if not context_text.strip():
            return QueryResponse(
                answer="Insufficient evidence: no matching local research records were retrieved. No scientific conclusion can be supported for this question.",
                citations=[], investigations_referenced=[], has_sufficient_evidence=False,
                notice="No evidence was retrieved; this system does not generate an unsupported answer."
            )
        if not self.client:
            raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY in backend/.env to use the research assistant.")

        system_instruction = (
            "You are FLAME INTELLIGENCE, a research assistant for microgravity combustion. Do not imply NASA endorsement.\n"
            "Your task is to answer the researcher's query accurately using strictly the provided NASA microgravity research context.\n"
            "STRICT RULES:\n"
            "1. Ground all answers strictly in the provided NASA context (FLEX, SAFFIRE, SPICE, BASS, ACME, etc.).\n"
            "2. Cite the specific investigation acronym and publication/DOI for every major scientific claim.\n"
            "3. Do not claim any local record or datapoint is a verified flight measurement. Distinguish documented facts, interpretation, assumptions, and unknowns.\n"
            "4. Never fabricate or invent experimental values, temperatures, burning rates, or citations.\n"
            "5. If the provided NASA records lack sufficient evidence to answer part of the question, explicitly state: 'The documented NASA microgravity records do not contain sufficient evidence for...'.\n"
            "6. Explain clearly why the finding is relevant to spacecraft fire safety.\n"
            "7. Remind the researcher that findings are scientific research insights and not certified spacecraft engineering waivers."
        )

        user_prompt = (
            f"RESEARCH CONTEXT:\n{context_text}\n\n"
            f"RESEARCH QUESTION: {question}\n\n"
            "Provide a rigorous, structured scientific response with headings, bullet points, citations, and spacecraft fire safety implications."
        )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=f"{system_instruction}\n\n{user_prompt}",
            )
            answer_text = response.text if response.text else "Gemini returned an empty response. No analysis is available."
            return QueryResponse(
                answer=answer_text,
                citations=citations,
                investigations_referenced=acronyms,
                has_sufficient_evidence=bool(citations and response.text)
            )
        except Exception as exc:
            http_status = getattr(exc, "status_code", None)
            if not isinstance(http_status, int):
                http_status = getattr(exc, "code", None)
            if not isinstance(http_status, int):
                http_status = "unavailable"
            logger.error(
                "Gemini API call failed: model=%s error_type=%s provider_http_status=%s",
                self.model,
                type(exc).__name__,
                http_status,
            )
            raise RuntimeError("Gemini research analysis is temporarily unavailable.") from exc
