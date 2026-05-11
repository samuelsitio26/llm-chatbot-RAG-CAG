import os
import sys
import io
import json
import time
import re
import string
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.append(os.path.abspath('src'))
from hybrid_system import CAGSystem
from model import GeminiChatModel
from langchain_huggingface import HuggingFaceEmbeddings

def normalize_answer(s):
    def remove_articles(text):
        return re.sub(r'\b(a|an|the)\b', ' ', text)
    def white_space_fix(text):
        return ' '.join(text.split())
    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)
    def lower(text):
        return text.lower()
    return white_space_fix(remove_articles(remove_punc(lower(str(s)))))

def exact_match_score(prediction, ground_truth):
    return (normalize_answer(prediction) == normalize_answer(ground_truth))

def f1_score(prediction, ground_truth):
    prediction_tokens = normalize_answer(prediction).split()
    ground_truth_tokens = normalize_answer(ground_truth).split()
    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0
    precision = 1.0 * num_same / len(prediction_tokens)
    recall = 1.0 * num_same / len(ground_truth_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1

def evaluate_dataset(system, dataset_name, dataset_path, num_samples=10):
    print(f"\n{'='*50}")
    print(f"Evaluating on {dataset_name}")
    print(f"{'='*50}")
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    qas = []
    if 'data' in data:  # SQuAD
        for article in data['data']:
            for paragraph in article['paragraphs']:
                for qa in paragraph['qas']:
                    if not qa.get('is_impossible', False) and len(qa['answers']) > 0:
                        qas.append({
                            'question': qa['question'],
                            'answers': [a['text'] for a in qa['answers']]
                        })
                    if len(qas) >= num_samples: break
                if len(qas) >= num_samples: break
            if len(qas) >= num_samples: break
    elif isinstance(data, list): # HotpotQA
        for item in data:
            qas.append({
                'question': item['question'],
                'answers': [item['answer']]
            })
            if len(qas) >= num_samples: break
                
    total_em = 0
    total_f1 = 0
    
    for i, item in enumerate(qas):
        question = item['question']
        gold_answers = item['answers']
        
        response = system.get_response(query=question)
        pred_answer = response.get('response', '')
        
        best_f1 = max([f1_score(pred_answer, a) for a in gold_answers])
        best_em = max([exact_match_score(pred_answer, a) for a in gold_answers])
        
        total_em += best_em
        total_f1 += best_f1
        
        print(f"\n[{i+1}/{num_samples}] Q: {question}")
        print(f"Gold: {gold_answers[0]}")
        print(f"Pred: {pred_answer[:150]}...")
        print(f"Score - F1: {best_f1:.2f} | EM: {int(best_em)}")
        
        time.sleep(2)
        
    avg_em = total_em / len(qas)
    avg_f1 = total_f1 / len(qas)
    print(f"\n--- RESULTS {dataset_name} ---")
    print(f"Avg EM: {avg_em:.4f} | Avg F1: {avg_f1:.4f}\n")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("Inisialisasi Model & Encoder...")
    model = GeminiChatModel(model_name="gemini-2.5-flash")
    encoder = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    system = CAGSystem(model=model, encoder=encoder)
    
    evaluate_dataset(system, "SQuAD", "datasets/squad/dev-v1.1.json", num_samples=10)
    evaluate_dataset(system, "HotpotQA", "datasets/hotpotqa/hotpot_dev_distractor_v1.json", num_samples=10)
