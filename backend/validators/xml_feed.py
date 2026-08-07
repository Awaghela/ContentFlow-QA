"""
XML Feed Validator
==================
Parses XML/JSON content feeds, validates against known XSD schemas,
checks encoding, namespace declarations, and required feed-level elements.
"""

from typing import Any
import xml.etree.ElementTree as ET
import json
import logging

logger = logging.getLogger(__name__)

# Minimal inline XSD-like rules (in production, load real .xsd files)
REQUIRED_XML_ELEMENTS = ["ContentID", "Title", "Genre", "Rating", "Duration"]
SUPPORTED_ENCODINGS = {"utf-8", "utf-16", "iso-8859-1"}


class XMLFeedValidator:
    """Validates XML and JSON feed files for schema compliance."""

    async def validate(self, assets: list[dict[str, Any]]) -> list[dict]:
        results = []
        for asset in assets:
            feed_content = asset.get("feed_xml") or asset.get("feed_json")
            feed_type = "xml" if asset.get("feed_xml") else "json"
            asset_id = asset.get("content_id", "unknown")

            if not feed_content:
                results.append(self._result(
                    asset_id, "feed_missing", "warn",
                    "No XML/JSON feed content associated with this asset",
                ))
                continue

            if feed_type == "xml":
                results.extend(self._validate_xml(asset_id, feed_content))
            else:
                results.extend(self._validate_json(asset_id, feed_content))

        return results

    def _validate_xml(self, asset_id: str, xml_str: str) -> list[dict]:
        issues = []

        # 1. Parse check
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            return [self._result(
                asset_id, "xml_parse_error", "fail",
                f"XML is malformed and could not be parsed: {e}",
                "Ensure the feed is well-formed XML before submission."
            )]

        issues.append(self._result(asset_id, "xml_well_formed", "pass", "XML is well-formed"))

        # 2. Encoding declaration
        if "encoding" in xml_str[:100].lower():
            enc_match = xml_str[:100].lower()
            if not any(enc in enc_match for enc in SUPPORTED_ENCODINGS):
                issues.append(self._result(
                    asset_id, "unsupported_encoding", "fail",
                    "XML declares an unsupported encoding",
                    f"Supported encodings: {', '.join(SUPPORTED_ENCODINGS)}"
                ))
        else:
            issues.append(self._result(
                asset_id, "no_encoding_declaration", "warn",
                "XML prolog does not declare an encoding; defaulting to UTF-8"
            ))

        # 3. Required elements
        tag_names = {child.tag.split("}")[-1] for child in root.iter()}
        for elem in REQUIRED_XML_ELEMENTS:
            if elem not in tag_names:
                issues.append(self._result(
                    asset_id, f"missing_element_{elem.lower()}", "fail",
                    f"Required XML element <{elem}> not found in feed",
                ))
            else:
                issues.append(self._result(
                    asset_id, f"element_{elem.lower()}_present", "pass",
                    f"Element <{elem}> found"
                ))

        # 4. Namespace check
        root_tag = root.tag
        if "{" not in root_tag:
            issues.append(self._result(
                asset_id, "no_namespace", "warn",
                "Root element has no XML namespace declaration",
                "Partners should use a versioned namespace URI."
            ))

        # 5. Empty text nodes
        empty_elems = [
            child.tag.split("}")[-1]
            for child in root.iter()
            if child.text is not None and child.text.strip() == "" and len(child) == 0
        ]
        if empty_elems:
            issues.append(self._result(
                asset_id, "empty_xml_elements", "warn",
                f"Empty elements found: {', '.join(empty_elems[:5])}",
                "Empty elements may indicate missing data."
            ))

        return issues

    def _validate_json(self, asset_id: str, json_str: str) -> list[dict]:
        issues = []
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return [self._result(
                asset_id, "json_parse_error", "fail",
                f"JSON feed is malformed: {e}",
            )]

        issues.append(self._result(asset_id, "json_valid", "pass", "JSON feed parsed successfully"))

        required_keys = ["content_id", "title", "genre", "rating"]
        for key in required_keys:
            if key not in data:
                issues.append(self._result(
                    asset_id, f"json_missing_{key}", "fail",
                    f"Required key '{key}' missing from JSON feed",
                ))

        return issues

    @staticmethod
    def _result(asset_id: str, scenario: str, status: str, message: str, detail: str = "") -> dict:
        return {
            "asset_id": asset_id,
            "scenario": scenario,
            "status": status,
            "message": message,
            "detail": detail,
        }
