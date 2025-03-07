import os
import requests
import traceback

import openai
import google.generativeai as genai


def make_gpt_messages(query, system, history):
    msgs = list()
    if system:
        msgs.append({
            "role": "system",
            "content": system
        })
    for q, a in history:
        msgs.append({
            "role": "user",
            "content": str(q)
        })
        msgs.append({
            "role": "assistant",
            "content": str(a)
        })
    msgs.append({
        "role": "user",
        "content": query
    })
    return msgs


def make_gemini_messages(query, system, history):
    assert not system
    msgs = list()
    for q, a in history:
        msgs.append({
            "role": "user",
            "parts": [str(q)],
        })
        msgs.append({
            "role": "model",
            "parts": [str(a)],
        })
    msgs.append({
        "role": "user",
        "parts": [query],
    })
    return msgs


class OpenAIClient(object):
    def __init__(self, model="gpt-3.5-turbo-1106"):
        self.model = model
        openai.api_type = os.environ.get("OPENAI_API_TYPE", "open_ai")
        openai.api_key = os.environ["OPENAI_API_KEY"]
        if openai.api_type == "azure":
            openai.api_version = os.environ["OPENAI_API_VERSION"]
            openai.api_base = os.environ["OPENAI_API_BASE"]

    def chat(self, query, history=list(), system="", temperature=0.0, stop="", *args, **kwargs):
        msgs = make_gpt_messages(query, system, history)

        try:
            if openai.api_type == "open_ai":
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=msgs,
                    temperature = temperature,
                    stop=stop
                    )
            elif openai.api_type == "azure":
                response = openai.ChatCompletion.create(
                    engine = self.model,
                    messages=msgs,
                    temperature = temperature,
                    stop=stop
                )
            response_text = response['choices'][0]['message']['content']
        except:
            print(traceback.format_exc())
            response_text = ""

        new_history = history[:] + [[query, response_text]]
        return response_text, new_history


# class OpenAIClient(object):
#     def __init__(self, model="gpt-3.5-turbo-1106"):
#         self.model = model
#         client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
#         self._client = client

#     def chat(self, query, history=list(), system="", temperature=0.0, stop="", *args, **kwargs):
#         msgs = make_gpt_messages(query, system, history)

#         try:
#             response = self._client.chat.completions.create(
#                 model=self.model,
#                 messages=msgs,
#                 temperature = temperature,
#                 stop=stop
#             )
#             response_text = response.choices[0].message.content
#         except:
#             print(traceback.format_exc())
#             response_text = ""
#         new_history = history[:] + [[query, response_text]]
#         return response_text, new_history


class GeminiClient(object):
    def __init__(self, model="gemini-pro"):
        self.model = model

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        self._client = genai.GenerativeModel(model)

    def chat(self, query, history=list(), system="", temperature=0.0, stop="", *args, **kwargs):
        msgs = make_gemini_messages(query, system, history)
        stop_sequences = []
        if stop:
            stop_sequences = [stop]
        gen_config = genai.types.GenerationConfig(
            candidate_count=1,
            stop_sequences=stop_sequences,
            temperature=temperature,
        )
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_ONLY_HIGH",
            },
        ]

        try:
            response = self._client.generate_content(
                msgs, generation_config=gen_config,
                safety_settings=safety_settings)
        except:
            print(response.prompt_feedback)
            print(traceback.format_exc())
            response = None

        if response is not None:
            try:
                response_text = response.text
            except:
                print(response.prompt_feedback)
                print(traceback.format_exc())
                response_text = ""
        else:
            response_text = ""
        
        print("Query start------------------")
        print(query)
        print("Query end--------------------")
        print("Response start---------------")
        print(response_text)
        print("Response end-----------------")

        new_history = history[:] + [[query, response_text]]
        return response_text, new_history

class FastChatClient(object):
    def __init__(self, model="kagentlms_baichuan2_13b_mat", host="localhost", port=8888):
        self.model = model
        self.host = host
        self.port = port

    def chat(self, query, history=list(), system="", temperature=0.0, stop="", *args, **kwargs):
        url = f'http://{self.host}:{self.port}/v1/completions/'

        headers = {"Content-Type": "application/json"}
        if "baichuan" in self.model:
            prompt = self.make_baichuan_prompt(query, system, history)
        elif "qwen" in self.model:
            prompt = self.make_qwen_prompt(query, system, history)
        else:
            prompt = self.make_prompt(query, system, history)
        data = {
            "model": self.model,
            "prompt": prompt,
            "temperature": 0.1,
            "top_p": 0.75,
            "top_k": 40,
            "max_tokens": 512
        }
        resp = requests.post(url=url, json=data, headers=headers)
        response = resp.json() # Check the JSON Response Content documentation below
        response_text = response['choices'][0]['text']

        new_history = history[:] + [[query, response_text]]
        return response_text, new_history

    @staticmethod
    def make_prompt(query, system, history):
        prompt = ""
        if not history:
            history = list()
        history = history + [(query, '')]
        for turn_idx, (q, r) in enumerate(history):
            if turn_idx == 0:
                prompt += system
            query = query + '<reserved_107>'

            prompt += 'User:' + q + '\nAssistant' + r + "\n"
        return prompt

    @staticmethod
    def make_baichuan_prompt(query, system, history):
        prompt = ""
        if not history:
            history = list()
        history = history + [(query, '')]
        for turn_idx, (q, r) in enumerate(history):
            if turn_idx == 0:
                prompt += system
            query = query + '<reserved_107>'

            prompt += '<reserved_106>' + q + '<reserved_107>' + r 
        return prompt

    @staticmethod
    def make_qwen_prompt(query, system, history):
        prompt = ""
        history = history + [(query, '')]
        for turn_idx, (q, r) in enumerate(history):
            if turn_idx == 0:
                prompt += '<|im_start|>' + system + '<|im_end|>\n'
            response = r if r else ''

            prompt += '<|im_start|>user\n' + q + '<|im_end|>\n<|im_start|>assistant\n' + response + "<|im_end|>\n"
        return prompt
