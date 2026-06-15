import re
import json

def generate_hint(answer_text):
    """
    Generates a hint from the answer text by showing the first 30% of the words,
    or masking characters.
    """
    words = answer_text.split()
    if len(words) <= 2:
        return "Подсказка: ответ состоит из " + str(len(words)) + " слов(а)."
    
    show_count = max(1, len(words) // 3)
    hint = " ".join(words[:show_count]) + "..."
    return f"Подсказка: начинается с '{hint}'"

def parse_markdown_to_json(md_file_path, json_file_path):
    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find all questions:
    # <details><summary><b>1.</b> Вопрос</summary><blockquote>Ответ</blockquote></details>
    pattern = re.compile(r'<details><summary><b>\d+\.</b>(.*?)</summary>\s*<blockquote>(.*?)</blockquote>\s*</details>', re.IGNORECASE | re.DOTALL)
    
    matches = pattern.findall(content)
    
    questions = []
    for idx, match in enumerate(matches, 1):
        question_text = match[0].strip()
        answer_text = match[1].strip()
        
        # Remove any lingering HTML tags inside the text for a clean bot output
        answer_text = re.sub(r'<[^>]+>', '', answer_text)
        question_text = re.sub(r'<[^>]+>', '', question_text)
        
        hint_text = generate_hint(answer_text)
        
        questions.append({
            "id": idx,
            "question": question_text,
            "answer": answer_text,
            "hint": hint_text
        })

    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=4)
        
    print(f"Successfully parsed {len(questions)} questions into {json_file_path}")

if __name__ == "__main__":
    import os
    # Default paths based on environment
    md_path = r"C:\Users\makst\.gemini\antigravity-cli\brain\329fdc26-5bdd-4124-b06c-a717034e502d\anatomy_biomechanics_quiz.md"
    json_path = os.path.join(os.path.dirname(__file__), "questions.json")
    parse_markdown_to_json(md_path, json_path)
