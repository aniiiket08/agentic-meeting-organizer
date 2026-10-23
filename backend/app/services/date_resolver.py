from datetime import datetime, timezone
import dateparser
from app.core.errors import ValidationFailed

class DateResolver:
    def resolve_date(self, relative_text: str, base_date: datetime | None = None) -> str:
        """Resolve relative date phrases like 'by Friday' or 'next week' into ISO YYYY-MM-DD format."""
        if not relative_text.strip():
            raise ValidationFailed("A due date phrase is required for date resolution.")
        if not base_date:
            base_date = datetime.now(timezone.utc)

        parsed = dateparser.parse(
            relative_text,
            settings={"RELATIVE_BASE": base_date, "PREFER_DATES_FROM": "future"}
        )

        if not parsed:
            raise ValidationFailed(
                f"Could not resolve due date phrase: {relative_text!r}.",
                details={"relative_text": relative_text},
            )
        return parsed.strftime("%Y-%m-%d")

date_resolver = DateResolver()
