import json
import logging
from datetime import datetime, timezone

from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy import select

from app.config import settings
from app.database import get_mongodb, async_session_maker
from app.models.call import Call

logger = logging.getLogger("voip.report_service")


class ReportService:
    """
    Generates post-call reports using LLM
    after the Twilio + Realtime call completes.
    """

    def __init__(self):
        if settings.azure_openai_api_key:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.azure_openai_deployment
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o"

    async def generate_report(
        self,
        call_sid: str,
        transcript: str,
        transcript_messages: list | None = None,
    ):
        if not transcript or not transcript.strip():
            logger.warning("empty_transcript_skipped", call_sid=call_sid)
            return

        try:
            # -----------------------------
            # 1. LLM Analysis
            # -----------------------------
            system_prompt = (
                "You are an expert real estate call analyst.\n\n"
                "Analyze the transcript of a phone call between an AI real estate assistant "
                "and a potential customer.\n\n"
                "Return a STRICT JSON object with the following fields:\n"
                "- summary (string)\n"
                "- customer_intent (string)\n"
                "- interest_level (High | Medium | Low)\n"
                "- follow_up_required (boolean)\n"
                "- action_items (array of strings)\n\n"
                "Do not include any extra text outside JSON."
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            raw_content = response.choices[0].message.content
            report_json = json.loads(raw_content)

            # -----------------------------
            # 2. Save to MongoDB
            # -----------------------------
            mongo = get_mongodb()

            report_doc = {
                "call_sid": call_sid,
                "transcript": transcript,
                "messages": transcript_messages or [],
                "analysis": report_json,
                "created_at": datetime.now(timezone.utc),
            }

            insert_result = await mongo.reports.insert_one(report_doc)
            report_id = str(insert_result.inserted_id)

            # -----------------------------
            # 3. Update SQL Call record
            # -----------------------------
            async with async_session_maker() as db:
                stmt = select(Call).where(Call.call_sid == call_sid)
                result = await db.execute(stmt)
                call = result.scalar_one_or_none()

                if call:
                    call.transcript_id = report_id
                    call.transcript_summary = report_json.get("summary", "")[:500]
                    call.outcome = report_json.get("customer_intent", "unknown")[:50]

                    call.outcome_notes = (
                        f"Interest: {report_json.get('interest_level')}\n"
                        f"Follow-up required: {report_json.get('follow_up_required')}"
                    )

                    await db.commit()

            logger.info(
                "report_generated_successfully",
                call_sid=call_sid,
                report_id=report_id,
            )

        except Exception as e:
            logger.exception(
                "report_generation_failed",
                call_sid=call_sid,
                error=str(e),
            )
