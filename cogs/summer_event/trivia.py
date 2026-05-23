import random 
from typing import Dict, List


class TriviaQuestion:

    def __init__(self, question: str, choices: List[str], answer: str):
        self.question = question 
        self.choices = choices
        self.answer = answer
    
    def shuffle_choices(self):
        random.shuffle(self.choices)

    def get_main_layout_repls(self) -> Dict[str, str]:
        repls = {"question": self.question}

        for i, choice in enumerate(self.choices):
            repls[f"choice{i+1}"] = choice
        
        return repls 

    def get_incorrect_layout_repls(self) -> Dict[str, str]:
        answer_index = self.choices.index(self.answer)

        match answer_index:
            case 0:
                answer_letter = "A"
            case 1:
                answer_letter = "B"
            case 2:
                answer_letter = "C"
            case 3:
                answer_letter = "D"

        return {
            "answer": self.answer,
            "answerletter": answer_letter,
        }


def parse_raw(filename: str = "cogs/activity_event/raw_trivia.txt") -> List[TriviaQuestion]:

    with open(filename) as f:
        text = f.read().strip()
    
    questions = [] 
    blocks = text.split("\n\n")
    for block in blocks:
        lines = block.split("\n")
        question = lines[0][3:]
        choices = lines[1:5]
        answer = choices[int(lines[5]) - 1]
        questions.append(TriviaQuestion(question, choices, answer))
    
    return questions 
