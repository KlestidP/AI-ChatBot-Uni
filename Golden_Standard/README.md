# Constructor University Bremen Info Bot

A Telegram chatbot that provides comprehensive information about Constructor University Bremen (formerly Jacobs University Bremen), including campus locations, dining schedules, locker access times, program handbooks, and more.

## Features

- **Campus Navigation**: Find locations and get directions around campus
- **Location Search**: Search for places with specific features (printers, food, study areas)
- **Dining Information**: Access servery hours for all colleges and the coffee bar
- **Locker Access**: Get locker access schedules for all college buildings
- **Program Handbooks**: Retrieve digital copies of program handbooks
- **University FAQs**: Answer common questions about university services
- **Multiple AI Providers**: Support for different language models (Mistral, OpenAI, Anthropic, Google)
- **University-Only Focus**: Content filtering to ensure responses stay relevant to university topics

## Architecture

The bot follows a tool-based architecture that routes queries to specialized handlers:

- **Tool Classification**: Automatically determines the type of query (location, handbook, etc.)
- **Vector Database**: Uses Supabase with pgvector for efficient document retrieval
- **LLM Integration**: Leverages language models for natural conversation and query handling
- **Conversation State**: Tracks conversation context for multi-step interactions

## Technical Stack

- **Python**: Core programming language
- **python-telegram-bot**: Telegram API integration
- **LangChain**: Framework for language model integration
- **Supabase**: Database and vector store
- **pgvector**: Vector similarity search in PostgreSQL
- **Mistral AI**: Default language model provider
- **OpenAI, Anthropic, Google**: Optional alternative AI providers

## Setup Instructions

### Prerequisites

- Python 3.8+
- Docker and Docker Compose (recommended for deployment)
- Telegram Bot Token
- Mistral AI API key
- Supabase account with pgvector extension enabled

### Environment Variables

Create a `.env` file with the following variables:

```
TELEGRAM_TOKEN=your_telegram_bot_token
MISTRAL_API_KEY=your_mistral_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
AI_PROVIDER=mistral  # optional, defaults to mistral
```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/uni-ai-chatbot.git
   cd uni-ai-chatbot
   ```

2. Set up a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python -m uni_ai_chatbot.scripts.init_setup
   ```

5. Run the bot:
   ```bash
   python -m uni_ai_chatbot.main
   ```

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. View logs:
   ```bash
   docker-compose logs -f
   ```

## Usage

### Available Commands

- `/start` - Start the bot
- `/help` - Get help using the bot
- `/where [location]` - Find a place on campus
- `/find [feature]` - Find places with specific features
- `/handbook [program]` - Get program handbooks
- `/provider [name] [api_key] [model]` - Change AI provider
- `/providers` - List available AI providers

### Example Queries

- "Where is the Ocean Lab?"
- "How do I get to College III from the main gate?"
- "Where can I find a printer?"
- "What are the locker hours for Krupp College?"
- "When is lunch served at Nordmetall?"
- "Can I get the Computer Science handbook?"
- "How do I get my enrollment certificate?"

## Extending the Bot

### Managing the Database

The bot uses Supabase with pgvector for storing and retrieving university information. Here's how to manage the data:

#### Updating Existing Data

1. **Update Data Source Files**:
   - Modify data in the appropriate source files:
     - Edit campus map data in `uni_ai_chatbot/data/campus_map_data.py`
     - Update locker hours in your Supabase `locker_hours` table
     - Update servery hours in your Supabase `servery_hours` table
     - Update FAQ responses in your Supabase `faq_responses` table

2. **Regenerate Embeddings**:
   ```bash
   python -m uni_ai_chatbot.scripts.update_supabase
   ```
   This will process updated data and recreate vector embeddings.

#### Adding New Document Types

1. **Create a Data Loader**:
   - Create a new loader file in the `data` directory (e.g., `my_data_loader.py`)
   - Implement a function to load and format your data

2. **Update the Preprocessing Script**:
   - Modify `uni_ai_chatbot/data/preprocess_supabase.py` to include your new data source:
   ```python
   # In the create_documents function
   from uni_ai_chatbot.data.my_data_loader import load_my_data
   
   # Add your new documents
   my_data = load_my_data()
   for item in my_data:
       documents.append(Document(
           page_content=f"Your formatted content here",
           metadata={
               "type": "your_data_type",
               "tool": "appropriate_tool_name",
               # Add other relevant metadata
           }
       ))
   ```

3. **Create a New Tool** (if needed):
   - If your new data requires specific handling, create a new tool as described in the section below
   - Update the tool classifier to route queries to your new tool

4. **Run the Database Update**:
   ```bash
   python -m uni_ai_chatbot.scripts.update_supabase
   ```

#### Modifying Schema

If you need to modify the database schema:

1. **Update pgvector Setup**:
   - Edit `uni_ai_chatbot/scripts/setup_pgvector.py` if you need to change the document table structure

2. **Execute SQL Directly**:
   - For complex schema changes, connect to your Supabase database and run SQL commands
   - You can use the Supabase web interface SQL editor
   
3. **Rebuild the Database**:
   ```bash
   # Drop existing tables and recreate them
   python -m uni_ai_chatbot.scripts.setup_pgvector
   
   # Regenerate all data and embeddings
   python -m uni_ai_chatbot.scripts.preprocess_supabase
   ```

### Adding New Tools

1. Create a new tool class in `uni_ai_chatbot/tools/tools_architecture.py`:
   ```python
   class YourNewTool(Tool):
       def __init__(self) -> None:
           super().__init__(
               name="your_tool_name",
               description="Description of what your tool does."
           )

       async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
           # Implement your tool's functionality here
   ```

2. Register the tool in `tool_registry`:
   ```python
   tool_registry.register_tool(YourNewTool())
   ```

### Adding AI Providers

To add support for a new AI provider:

1. Install the required package:
   ```bash
   pip install langchain_your_provider
   ```

2. Add the provider to `SUPPORTED_PROVIDERS` in `config.py`:
   ```python
   "your_provider": {
       "module": "langchain_your_provider",
       "embeddings": "YourProviderEmbeddings",
       "llm": "ChatYourProvider",
       "default_model": "your-model-name"
   }
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.