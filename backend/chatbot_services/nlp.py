import re
from typing import Optional, Dict, Tuple

def normalize_text(text: str) -> str:
    """
    Normalizes the input text for consistent processing.

    Operations:
    1. Converts to lowercase.
    2. Strips leading/trailing whitespace.
    3. Replaces multiple spaces with a single space.

    Args:
        text (str): The raw input string.

    Returns:
        str: The normalized string.
    """
    text = text.lower()
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_txn_id(text: str) -> Optional[str]:
    """
    Extracts a transaction ID from the given text using common prefixes.

    Supported formats include:
    - TXN123, txn 123
    - TXN-123, txn_123
    - transaction 001
    - trx 5678
    - txd_id 123 (typo support)

    Args:
        text (str): The input string to search.

    Returns:
        Optional[str]: Just the numeric transaction ID if found, otherwise None.

    Examples:
        "TXN123" -> "123"
        "txn-456" -> "456"
        "transaction id: 789" -> "789"
    """
    # Regex pattern to find prefixes followed by digits (including txd_id typo)
    pattern = r"\b(?:txn\s?id|txd[_\s]?id|txd|txn|transaction|trans|trx)[\s:_=-]*(\d+)\b"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_rrn(text: str) -> Optional[str]:
    """
    Extracts a 12-digit Retrieval Reference Number (RRN) from text.

    Looks for optional RRN prefix followed by exactly 12 digits.
    Also extracts standalone 12-digit numbers.

    Examples:
        "RRN 123456789012" -> "123456789012"
        "ref: 987654321098" -> "987654321098"
        "check 112233445566" -> "112233445566"

    Args:
        text (str): The input string.

    Returns:
        Optional[str]: The 12-digit number string if found, otherwise None.
    """
    # Look for optional RRN/ref prefix followed by 12 digits
    pattern = r"\b(?:rrn|ref(?:erence)?|retrieval)?\s*:?\s*(\d{12})\b"
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        rrn = match.group(1)
        return rrn if validate_rrn(rrn) else None

    return None


def validate_rrn(rrn: str) -> bool:
    """
    Validates that RRN is exactly 12 digits.

    Args:
        rrn (str): The RRN string to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    return bool(re.match(r'^\d{12}$', rrn))


def validate_txn_id(txn_id: str) -> bool:
    """
    Validates that transaction ID contains only digits.

    Args:
        txn_id (str): The transaction ID to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    # Accept either numeric IDs (e.g. '001') or IDs with an optional 'TXN' prefix (e.g. 'TXN001', 'txn001')
    return bool(re.match(r'^(?:txn)?\d+$', txn_id, re.IGNORECASE))


def detect_intent(text: str) -> Tuple[str, float]:
    """
    Detects the user intent from the query with confidence score.

    Args:
        text (str): The normalized user query.

    Returns:
        Tuple[str, float]: The identified intent and confidence score (0.0-1.0).

    Supported intents:
        - greeting: User greeting
        - status_check: Check transaction status
        - refund_request: Request refund
        - failure_inquiry: Ask about failed transaction
        - complaint: Lodge complaint
        - support_request: General support
        - unknown: Cannot determine intent
    """
    text = normalize_text(text)

    # Check for greeting
    if re.search(r'\b(hi|hello|hey|good\s?(morning|afternoon|evening)|namaste|greetings)\b', text):
        return ("greeting", 0.95)

    # Extract identifiers to check if transaction-related
    rrn = extract_rrn(text)
    txn = extract_txn_id(text)
    has_identifier = bool(rrn or txn)

    # Transaction-specific intents
    if has_identifier:
        if re.search(r'\b(refund|return|money\s?back|reverse|cancel|reimburs)', text):
            return ("refund_request", 0.9)
        elif re.search(r'\b(status|check|track|update|where|locate|find)', text):
            return ("status_check", 0.9)
        elif re.search(r'\b(fail(?:ed|ure)?|unsuccessful|decline|reject|error)', text):
            return ("failure_inquiry", 0.85)
        elif re.search(r'\b(complain|complaint|escalat|disappointed|upset)', text):
            return ("complaint", 0.8)

    # General support patterns
    if re.search(r'\b(help|support|assist|issue|problem|query|question)', text):
        confidence = 0.8 if has_identifier else 0.6
        return ("support_request", confidence)

    # Check for refund without identifier (lower confidence)
    if re.search(r'\b(refund|return|money\s?back)', text):
        return ("refund_request", 0.6)

    # Check for status without identifier (lower confidence)
    if re.search(r'\b(status|check|track)', text):
        return ("status_check", 0.5)

    return ("unknown", 0.3)


def extract_identifiers(text: str) -> Dict[str, any]:
    """
    Extracts all transaction identifiers and intent from text.

    Args:
        text (str): The raw input string.

    Returns:
        Dict: Dictionary containing extracted information.

    Example:
        >>> extract_identifiers("Check status of TXN12345")
        {
            'normalized_text': 'check status of txn12345',
            'txn_id': '12345',
            'rrn': None,
            'intent': 'status_check',
            'confidence': 0.9,
            'has_identifier': True
        }
    """
    normalized = normalize_text(text)
    txn_id = extract_txn_id(normalized)
    rrn = extract_rrn(normalized)
    intent, confidence = detect_intent(normalized)

    return {
        'normalized_text': normalized,
        'txn_id': txn_id,
        'rrn': rrn,
        'intent': intent,
        'confidence': confidence,
        'has_identifier': bool(txn_id or rrn)
    }
