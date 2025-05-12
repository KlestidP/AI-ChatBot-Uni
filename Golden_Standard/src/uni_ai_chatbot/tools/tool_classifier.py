import logging
from langchain_mistralai import ChatMistralAI
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class ToolClassifier:
    """
    A class that uses LLM to classify user queries and select appropriate tools
    """

    def __init__(self, llm: ChatMistralAI = None):
        self.llm = llm
        from uni_ai_chatbot.tools.tools_architecture import tool_registry
        self._tools = tool_registry.get_tool_descriptions()

    async def classify_query(self, query: str) -> str:
        """
        Classify a user query to determine which tool should handle it
        Prioritizes LLM classification if available, falls back to basic rules
        """
        # Use the LLM if available - give this higher priority
        if self.llm:
            try:
                classification_prompt = self._build_classification_prompt(query)
                response = self.llm.invoke(classification_prompt)
                tool_name = self._parse_classification_response(response.content)
                logger.info(f"LLM classified query '{query}' as '{tool_name}'")
                return tool_name
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}, falling back to basic rules")

        # Fall back to basic rules if LLM is not available or fails
        query_lower = query.lower()

        # Basic location detection
        location_terms = ["where", "find", "location"]
        if any(term in query_lower for term in location_terms):
            return "location"

        # Basic locker detection
        if "locker" in query_lower:
            return "locker"

        # Default to general QA
        return "qa"

    def _build_classification_prompt(self, query: str) -> str:
        """
        Build a prompt for the LLM to classify the query
        """
        # Create a detailed prompt with examples for better classification
        tool_descriptions = "\n\n".join([
            f"Tool: {tool['name']}\nDescription: {tool['description']}"
            for tool in self._tools
        ])

        # Add examples to help the model understand common patterns
        examples = """
Examples:
1. "Where is the library?" → location
2. "How do I get my enrollment certificate?" → faq
3. "When are the locker hours for Krupp College?" → locker
4. "What's the address of the university?" → qa
5. "Where can I print documents?" → location
6. "Tell me about the semester ticket" → faq
7. "How to change my address in Bremen?" → faq
8. "What's the student emergency number?" → faq
9. "Where can I get food on campus?" → location
"""

        return f"""You are a query classifier for a university chatbot. Your task is to classify the user's query into one of the available tools based on its intent.

Available tools:
{tool_descriptions}

{examples}

User query: "{query}"

Analyze the query and determine which tool is most appropriate to handle it. Respond with just the tool name and nothing else. The available tools are: location, locker, faq, qa.
"""

    def _parse_classification_response(self, response: str) -> str:
        """
        Parse the LLM's response to extract the tool name
        """
        # Clean the response text
        response = response.strip().lower()

        # Check if the response contains any of our tool names
        valid_tools = ["location", "locker", "faq", "qa"]
        for tool_name in valid_tools:
            if tool_name in response:
                return tool_name

        # If no match found, default to qa
        return "qa"


async def get_appropriate_tool(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """
    Determine the appropriate tool to handle a user query using AI
    """
    # Initialize the classifier if it doesn't exist in bot_data
    if "tool_classifier" not in context.bot_data:
        llm = None
        if "llm" in context.bot_data:
            llm = context.bot_data["llm"]
        context.bot_data["tool_classifier"] = ToolClassifier(llm)

    # Classify the query
    classifier = context.bot_data["tool_classifier"]
    tool_name = await classifier.classify_query(query)

    # Get the appropriate tool from the registry
    from uni_ai_chatbot.tools.tools_architecture import tool_registry
    tool = tool_registry.get_tool_by_name(tool_name)

    # If no tool found, default to QA
    if not tool:
        tool = tool_registry.get_tool_by_name("qa")

    return tool