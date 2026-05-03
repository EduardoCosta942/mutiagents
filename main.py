from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
from datetime import datetime, date;
from prompts import *
from faq_tools import faq_retriever
 
load_dotenv()
 
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    top_p=0.95,
    google_api_key=os.getenv("GEMINI_API_KEY")
)
 
llm_groq = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.7,
    groq_api_key=os.getenv("GROQ_API_KEY")
)
 
agora = datetime.now().strftime('%H:%M:%S')
hoje = date.today()
 
llm_especialista = llm_gemini.with_fallbacks([llm_groq])
 
llm_rapido = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.0,
    api_key=os.getenv("GROQ_API_KEY")
)
 
router_memory = MemorySaver()
 
checkpointer = MemorySaver()
router_app = create_agent(
    model=llm_rapido,
    system_prompt=ROUTER_PROMPT_COMPLETO,
    checkpointer=router_memory,
)
 
financeiro_app = create_agent(
    model=llm_especialista,
    tools=[],
    system_prompt=FINANCEIRO_PROMPT_COMPLETO,
)
 
agenda_app = create_agent(
    model=llm_especialista,
    tools=[],
    system_prompt=AGENDA_PROMPT_COMPLETO,
)

faq_app = create_agent(
    model=llm_rapido,
    tools=[faq_retriever],
    system_prompt=FAQ_PROMPT_COMPLETO,
)
 
orquestrador_app = create_agent(
    model=llm_rapido,
    system_prompt=ORQUESTRADOR_PROMPT_COMPLETO,
)
 
def executar_fluxo(input, sid):
    resp_router = router_app.invoke(
        { "messages": [{ "role": "human", "content": input}]},
        config={ "configurable": { "thread_id": "meu_id_de_sessao" } }
    )
   
    if "ROUTE=" not in resp_router['messages'][-1].content:
        return resp_router['messages'][-1].content

    resp_financeiro = None
    resp_agenda = None
    resp_faq = None
    resp_orquestrador = None

    if "ROUTE=financeiro" in resp_router['messages'][-1].content:
        resp_financeiro = financeiro_app.invoke(
            { "messages": [{ "role": "human", "content": resp_router['messages'][-1].content }] }
        )
        print("Resposta financeiro: ", resp_financeiro['messages'][-1].content)
    elif "ROUTE=agenda" in resp_router['messages'][-1].content:
        resp_agenda = agenda_app.invoke(
            { "messages": [{ "role": "human", "content": resp_router['messages'][-1].content }] }
        )
        print("Resposta agenda: ", resp_agenda['messages'][-1].content)
    elif "ROUTE=faq" in resp_router['messages'][-1].content:
        resp_faq = faq_app.invoke(
            { "messages": [{ "role": "human", "content": resp_router['messages'][-1].content }] }
        )
        return resp_faq['messages'][-1].content
    
    if resp_financeiro or resp_agenda:
        resp_orquestrador = orquestrador_app.invoke(
            { "messages": [{ "role": "human", "content": f"Resposta financeiro: {resp_financeiro['messages'][-1].content if resp_financeiro else ''}\nResposta agenda: {resp_agenda['messages'][-1].content if resp_agenda else ''}" }] }
        )
    return resp_orquestrador['messages'][-1].text if resp_orquestrador else "Desculpe, não consegui processar sua solicitação."
            

while True:
    print("\033[32m", end="")
    user_input= input("> ")
    print("\033[0m", end="")
    if user_input.lower() in ('sair', 'end', 'fim', 'tchau', 'bye', 'exit'):
        print("Encerrando...")
        break
    try:
        resposta = executar_fluxo(input=user_input, sid="id_do_usuario")
        print(resposta);
    except Exception as e:
        print("Erro ao consumir a API: ", e)