from difflib import SequenceMatcher
from typing import List, Tuple

class SimilarityDetector:
    @staticmethod
    def similarity_score(text1: str, text2: str) -> float:
        t1 = " ".join(text1.lower().split())
        t2 = " ".join(text2.lower().split())

        seq = SequenceMatcher(None, t1, t2).ratio()

        words1 = set(t1.split())
        words2 = set(t2.split())
        jaccard = len(words1 & words2) / len(words1 | words2) if words1 or words2 else 0

        return seq * 0.7 + jaccard * 0.3

    @staticmethod
    def find_similar_cases(description: str, entries: List[dict], threshold: float = 0.6) -> List[Tuple[str, float]]:
        similar = []
        for entry in entries:
            if entry.get("systemic_key"):
                continue
            score = SimilarityDetector.similarity_score(description, entry.get("description", ""))
            if score >= threshold:
                similar.append((entry["entry_id"], score))
        return sorted(similar, key=lambda x: x[1], reverse=True)