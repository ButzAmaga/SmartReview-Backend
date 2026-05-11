

from contextlib import asynccontextmanager
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from peft import PeftModel
from fastapi import FastAPI
import torch

# Dictionary to hold the model and tokenizer
ml_models = {}
model_path = '../../flan t5 large'
lora_path = '../../Flan T5 Model/flan_t5_lora_large'

@asynccontextmanager
async def lifespan(app: FastAPI):

    # 1. Load base model
    base_model_name = model_path

    model = AutoModelForSeq2SeqLM.from_pretrained(base_model_name, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, local_files_only=True)

    # 2. Load LoRA weights
    model = PeftModel.from_pretrained(model, lora_path, local_files_only=True)

    # 3. (Optional) merge LoRA into base model for faster inference
    model = model.merge_and_unload()
    
    ml_models["tokenizer"] = tokenizer
    ml_models["model"] = model
    
    yield
    # Clean up and release resources on shutdown
    ml_models.clear()


def generate_qa(input_text):
    # Preprocess the input text similar to how the training data was structured
    prompt = (
        "Task: Extract a factual question and a concise answer from the provided text.\n"
        "Format: Q: <QUESTION> A: <ANSWER>\n\n"
        "Example:\n"
        "Text: The Eiffel Tower was completed in 1889 and is located in Paris.\n"
        "Q: In what year was the Eiffel Tower completed?\n"
        "A: 1889\n\n"
        f"Text:{input_text}\nQ:"
    )

    # Tokenize the input
    inputs = ml_models["tokenizer"](
        prompt,
        truncation=True,
        return_tensors="pt"
    )

    # Move each tensor to model.device
    inputs = {k: v.to(ml_models["model"].device) for k, v in inputs.items()}

    # Generate output using the fine-tuned model
    with torch.no_grad():
        outputs = ml_models["model"].generate(
            **inputs,
            max_new_tokens=512,
            num_beams=3, # You can adjust this for more diverse or precise outputs
            #do_sample=True, # Set to True for sampling, False for greedy decoding
            #num_return_sequences=3,  # Generates 3 different sequences
            # N-Gram Blocking: Prevents any sequence of 3 words from appearing twice
            #no_repeat_ngram_size=3, 
            # Repetition Penalty: Penalizes tokens that have already appeared (1.0 is neutral)
            # repetition_penalty=1.2, 
            #temperature=0.7, # Adjust for creativity
            #top_k=50, # Limit to top k tokens
            #top_p=0.95 # Nucleus sampling
        )

    # Decode the generated tokens
    decoded_output = ml_models["tokenizer"].decode(outputs[0], skip_special_tokens=True)


    return decoded_output

def generate_qa_sequences(input_text):
    # Preprocess the input text similar to how the training data was structured
    prompt = (
        "Task: Extract a factual question and a concise answer from the provided text.\n"
        "Format: Q: <QUESTION> A: <ANSWER>\n\n"
        "Example:\n"
        "Text: The Eiffel Tower was completed in 1889 and is located in Paris.\n"
        "Q: In what year was the Eiffel Tower completed?\n"
        "A: 1889\n\n"
        f"Text:{input_text}\nQ:"
    )

    # Tokenize the input
    inputs = ml_models["tokenizer"](
        prompt,
        truncation=True,
        return_tensors="pt"
    )

    # Move each tensor to model.device
    inputs = {k: v.to(ml_models["model"].device) for k, v in inputs.items()}

    # Generate output using the fine-tuned model
    with torch.no_grad():
        outputs = ml_models["model"].generate(
            **inputs,
            max_new_tokens=120,
            #num_beams=2, # You can adjust this for more diverse or precise outputs
            do_sample=True, # Set to True for sampling, False for greedy decoding
            num_return_sequences=3,  # Generates 3 different sequences
            # N-Gram Blocking: Prevents any sequence of 3 words from appearing twice
            no_repeat_ngram_size=3, 
            # Repetition Penalty: Penalizes tokens that have already appeared (1.0 is neutral)
            repetition_penalty=1.2, 
            #temperature=0.7, # Adjust for creativity
            #top_k=50, # Limit to top k tokens
            #top_p=0.95 # Nucleus sampling
        )

    # Decode the generated tokens
    decoded_output = ml_models["tokenizer"].batch_decode(outputs, skip_special_tokens=True)


    return decoded_output


def generate_qa_batch_t5(input_texts):
    # 1. T5 uses right padding by default, which is standard for its encoder
    ml_models["tokenizer"].padding_side = "right" 

    prompts = []

    for input_text in input_texts:
        prompt = (
            "Task: Extract a factual question and a concise answer from the provided text.\n"
            "Format: Q: <QUESTION> A: <ANSWER>\n\n"
            "Example:\n"
            "Text: The Eiffel Tower was completed in 1889 and is located in Paris.\n"
            "Q: In what year was the Eiffel Tower completed?\n"
            "A: 1889\n\n"
            f"Text:{input_text}\nQ:"
        )
        prompts.append(prompt)


    # 3. Tokenize with padding and attention masks
    inputs = ml_models["tokenizer"](
        prompts,
        padding=True,
        truncation=True,
        return_tensors="pt"
    ).to(ml_models["model"].device)

    # 4. Generate
    with torch.no_grad():
        outputs = ml_models["model"].generate(
            **inputs,
            max_new_tokens=512,
            num_beams=3 # more diverse selection of output
            # no_repeat_ngram_size=3,
            # repetition_penalty=1.5,
            # do_sample=True, # Set to True for sampling, False for greedy decoding
            # num_return_sequences=2,  # Generates 3 different sequences
            # temperature=0.4, # add variety to words
            # T5 often benefits from these for factual tasks
            # length_penalty=1.0, 
        )

    # 5. Decode
    return ml_models["tokenizer"].batch_decode(outputs, skip_special_tokens=True)

def generate_qa_batch_t5_v2(input_texts):
    # 1. T5 uses right padding by default, which is standard for its encoder
    ml_models["tokenizer"].padding_side = "right" 

    
    # 1. Create a list of prompts for every item in your array
    prompts = [
        (
        f"Generate QA pair based on context. Follow the format Q: [question] A: [answer].\n\n"
        "Context: The old attic was silent until Maya heard something shift behind a stack of dusty crates.\n"
        "Q: What was silent until Maya heard something? A: old attic.\n\n"
        f"Context: {text}\nQ:"
        )
        for text in input_texts
    ]

    # 3. Tokenize with padding and attention masks
    inputs = ml_models["tokenizer"](
        prompts,
        padding=True,
        truncation=True,
        return_tensors="pt"
    ).to(ml_models["model"].device)

    # 4. Generate
    with torch.no_grad():
        outputs = ml_models["model"].generate(
            **inputs,
            max_new_tokens=512,
            # num_beams=3 # more diverse selection of output
            # no_repeat_ngram_size=3,
            # repetition_penalty=1.5,
            # do_sample=True, # Set to True for sampling, False for greedy decoding
            # num_return_sequences=2,  # Generates 3 different sequences
            # temperature=0.4, # add variety to words
            # T5 often benefits from these for factual tasks
            # length_penalty=1.0, 
        )

    # 5. Decode
    return ml_models["tokenizer"].batch_decode(outputs, skip_special_tokens=True)
