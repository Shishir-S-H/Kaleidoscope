# Shared Package for Kaleidoscope AI Microservices
# This package contains shared models, utilities, and configurations

# Avoid importing heavy model dependencies at package import time.
# Services that need AI models can import from shared.models directly.
try:
	from .models import (
		BaseAIModel,
		get_model_registry,
		get_image_captioning_model,
		get_face_recognition_model,
	)
	__all__ = [
		'BaseAIModel',
		'get_model_registry',
		'get_image_captioning_model',
		'get_face_recognition_model',
	]
except Exception:
	# Defer heavy imports for services that don't need them (e.g., orchestrator DB models)
	__all__ = []
