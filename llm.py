from config import GROQ_API_KEY, GROQ_MODEL
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

AGENT_PROMPT = """You are {agent_name}, a live SunBun Solar support agent.
Be warm, professional and empathetic. Keep replies concise (2-4 sentences).
Customer context: {context}"""

llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.5)

def get_agent_reply(agent_name: str, context: str, history: list) -> str:
    try:
        msgs = [SystemMessage(content=AGENT_PROMPT.format(agent_name=agent_name, context=context))]
        for msg in history:
            msgs.append(HumanMessage(content=msg["content"]) if msg["role"] == "user" 
                       else AIMessage(content=msg["content"]))
        return llm.invoke(msgs).content.strip()
    except Exception:
        return f"Hi, I'm {agent_name} from SunBun Solar. How can I help you today?"