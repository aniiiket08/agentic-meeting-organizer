import logging
import re
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("meeting_organizer")


class GroundingChecker:
    def verify_grounding(self, transcript: str, items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Require a verbatim quote and timestamp to occur on the same transcript line.
        Returns (valid_items, dropped_items).
        """
        valid_items = []
        dropped_items = []

        for index, item in enumerate(items):
            quote = item.get("source_quote", "").strip()
            timestamp = item.get("timestamp")
            timestamp = timestamp.strip() if isinstance(timestamp, str) else None
            if not quote:
                logger.warning(
                    "Dropped ungrounded item index=%d: source quote is missing.",
                    index,
                )
                dropped_items.append(item)
                continue

            quote_clean = " ".join(quote.split())
            timestamp_clean = re.sub(r"[\[\]]", "", timestamp) if timestamp else None
            grounded = False
            for line in transcript.splitlines():
                normalized_line = " ".join(line.split())
                if quote_clean in normalized_line and (
                    timestamp_clean is None or timestamp_clean in normalized_line
                ):
                    grounded = True
                    break
            if grounded:
                valid_items.append(item)
            else:
                logger.warning(
                    "Dropped ungrounded item index=%d: quote and timestamp do not match a transcript line.",
                    index,
                )
                dropped_items.append(item)

        return valid_items, dropped_items

grounding_checker = GroundingChecker()
