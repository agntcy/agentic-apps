import os
import logging

logger = logging.getLogger(__name__)

def create_llm_model(agent_type: str = "default"):
    """
    Create an LLM model instance based on environment configuration.

    Supports:
    - Azure OpenAI (provider="azure")
    - Google Gemini (provider="google" or "gemini")

    Args:
        agent_type: The type of agent (guide, tourist, scheduler) to look for specific env vars.
                    e.g. GUIDE_MODEL, TOURIST_MODEL, SCHEDULER_MODEL
    """
    from google.adk.models.lite_llm import LiteLlm

    # Determine provider
    provider = os.getenv("MODEL_PROVIDER", "azure").lower()

    # Determine model name
    # 1. Try specific agent model var (e.g. GUIDE_MODEL)
    # 2. Try generic MODEL_NAME
    # 3. Fallback based on provider
    env_var_prefix = agent_type.upper()
    model_name = os.getenv(f"{env_var_prefix}_MODEL")
    if not model_name:
        model_name = os.getenv("MODEL_NAME")

    if provider in ["google", "gemini"]:
        if not model_name:
            model_name = "gemini/gemini-3-pro-preview"

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set for Gemini model")

        logger.info(f"Creating Gemini model: {model_name}")
        return LiteLlm(
            model=model_name,
            api_key=api_key
        )

    elif provider == "azure":
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        if not model_name:
            model_name = f"azure/{deployment_name}"

        api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
        api_base = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_API_BASE")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv("AZURE_API_VERSION", "2024-02-01")

        logger.info(f"Creating Azure OpenAI model: {model_name}")
        return LiteLlm(
            model=model_name,
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
        )

    else:
        # Generic fallback for other providers supported by LiteLLM
        if not model_name:
            model_name = "gpt-3.5-turbo" # Fallback

        logger.info(f"Creating generic LiteLLM model: {model_name}")
        return LiteLlm(model=model_name)
