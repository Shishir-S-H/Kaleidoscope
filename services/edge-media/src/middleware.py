from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger('edge-media.consent')

class ConsentMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        consent_header = request.headers.get('X-Consent-Granted', 'false')
        if consent_header.lower() != 'true':
            logger.warning('Request rejected: Consent not granted. IP and PII stripped from logs.')
            return JSONResponse({"error": "Consent denied. Processing halted immediately."}, status_code=403)
        return await call_next(request)
