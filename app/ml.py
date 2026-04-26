

from contextlib import asynccontextmanager
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from peft import PeftModel
from fastapi import FastAPI
import torch

# Dictionary to hold the model and tokenizer
ml_models = {}
model_path = '../../flan t5 base'
lora_path = '../../Flan T5 Model/flan_t5_lora_base'

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
            #num_beams=2, # You can adjust this for more diverse or precise outputs
            #do_sample=True, # Set to True for sampling, False for greedy decoding
            #temperature=0.7, # Adjust for creativity
            #top_k=50, # Limit to top k tokens
            #top_p=0.95 # Nucleus sampling
        )

    # Decode the generated tokens
    decoded_output = ml_models["tokenizer"].decode(outputs[0], skip_special_tokens=True)


    return decoded_output


