import logging
import importlib
from typing import Optional, Tuple, Any
from langchain_mistralai import MistralAIEmbeddings

from uni_ai_chatbot.configurations.config import SUPPORTED_PROVIDERS, DEFAULT_PROVIDER, MISTRAL_API_KEY

logger = logging.getLogger(__name__)


def dynamic_import_provider(provider_name):
    """Dynamically import provider modules when needed"""
    if provider_name not in SUPPORTED_PROVIDERS:
        logger.warning(f"Provider {provider_name} not supported")
        return None, None
    provider_info = SUPPORTED_PROVIDERS[provider_name]
    module_name = provider_info["module"]
    try:
        module = importlib.import_module(module_name)
        # Get embeddings class if available
        embeddings_class = None
        if provider_info["embeddings"]:
            embeddings_class = getattr(module, provider_info["embeddings"])
        # Get LLM class
        llm_class = getattr(module, provider_info["llm"])
        return embeddings_class, llm_class
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing {provider_name} provider: {e}")
        return None, None


def get_embeddings_model(provider=None, api_key=None):
    """Get the appropriate embeddings model based on the provider"""
    # Use system default if no provider specified
    if not provider:
        provider = DEFAULT_PROVIDER
        api_key = MISTRAL_API_KEY
    # Special case for Anthropic which doesn't have embeddings
    if provider == "anthropic":
        # Fall back to Mistral embeddings if available
        if MISTRAL_API_KEY:
            return MistralAIEmbeddings(api_key=MISTRAL_API_KEY)
        # Or try OpenAI
        try:
            EmbeddingsClass, _ = dynamic_import_provider("openai")
            if EmbeddingsClass and api_key:
                return EmbeddingsClass(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to use OpenAI embeddings: {e}")
        raise ValueError("Cannot use Anthropic without embeddings from another provider")
    # For other providers
    EmbeddingsClass, _ = dynamic_import_provider(provider)
    if not EmbeddingsClass:
        raise ValueError(f"No embeddings class found for provider {provider}")
    return EmbeddingsClass(api_key=api_key)


def get_llm_model(provider=None, api_key=None, model=None):
    """Get the appropriate language model based on the provider"""
    # Use system default if no provider specified
    if not provider:
        provider = DEFAULT_PROVIDER
        api_key = MISTRAL_API_KEY
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    # Get the LLM class for this provider
    _, LLMClass = dynamic_import_provider(provider)
    if not LLMClass:
        raise ValueError(f"Failed to import LLM class for {provider}")
    # Get default model for the provider if not specified
    if not model:
        model = SUPPORTED_PROVIDERS[provider]["default_model"]
    # Create the LLM instance with appropriate parameters
    return LLMClass(
        model=model,
        temperature=0,
        api_key=api_key
    )
