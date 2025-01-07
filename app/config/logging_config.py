import json
import logging
import datetime

class JsonFormatter(logging.Formatter):
    """JSON log formatter"""
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage()
        }
        # Add exception info if present
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logging(settings):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)
    
    # Also set uvicorn access logger
    logging.getLogger("uvicorn.access").setLevel("INFO")