# File: app/scripts/training/fine_tune_embeddings.py
"""
Fine-tune Sentence Transformers for Internship-Student Matching
Uses Contrastive Learning with hard negative mining
"""

import os
import json
import random
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from tqdm import tqdm
import logging
from collections import defaultdict

from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
    evaluation,
    models
)
from sentence_transformers.losses import ContrastiveLoss, CosineSimilarityLoss
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
MODEL_DIR = PROJECT_ROOT / "models"
FINE_TUNED_DIR = MODEL_DIR / "fine_tuned"

for d in [MODEL_DIR, FINE_TUNED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

print(f"Project root: {PROJECT_ROOT}")
print(f"Data directory: {DATA_DIR}")
print(f"Fine-tuned model directory: {FINE_TUNED_DIR}")


@dataclass
class FineTuningConfig:
    """Configuration for fine-tuning"""
    base_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    output_model_name: str = "yuvasetu-embeddings-v1"
    
    # Training parameters
    epochs: int = 3
    batch_size: int = 32
    learning_rate: float = 2e-5
    warmup_steps: int = 100
    weight_decay: float = 0.01
    
    # Loss configuration
    loss_type: str = "multiple_negatives"  # contrastive, cosine, multiple_negatives
    
    # Data parameters
    max_seq_length: int = 256
    train_split: float = 0.8
    
    # Hard negative mining
    num_hard_negatives: int = 3
    use_hard_negatives: bool = True
    
    # Evaluation
    evaluation_steps: int = 500
    
    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class MatchingDataset:
    """Dataset for student-internship matching"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.students = []
        self.internships = []
        self.matches = []
        self.student_lookup = {}
        self.internship_lookup = {}
        
    def load(self):
        """Load data from files"""
        logger.info("Loading training data...")
        
        train_dir = self.data_dir / "train"
        if not train_dir.exists():
            raise FileNotFoundError(
                f"Training data not found at {train_dir}\n"
                f"Run: python app/scripts/data/generate_synthetic_dataset.py"
            )
        
        with open(train_dir / "students.json") as f:
            self.students = json.load(f)
        with open(train_dir / "internships.json") as f:
            self.internships = json.load(f)
        with open(train_dir / "matches.json") as f:
            self.matches = json.load(f)
        
        self.student_lookup = {s["id"]: s for s in self.students}
        self.internship_lookup = {i["id"]: i for i in self.internships}
        
        logger.info(f"Loaded: {len(self.students)} students, {len(self.internships)} internships, {len(self.matches)} matches")
    
    def student_to_text(self, student: Dict) -> str:
        """Convert student profile to text"""
        parts = []
        
        # Skills
        if student.get("skills"):
            skill_names = [s["name"] if isinstance(s, dict) else s for s in student["skills"]]
            parts.append(f"Skills: {', '.join(skill_names)}")
        
        # Education
        if student.get("education"):
            for edu in student["education"][:1]:  # Take first education
                parts.append(f"Education: {edu.get('degree', '')} in {edu.get('field_of_study', '')} from {edu.get('institution', '')}")
        
        # Experience
        if student.get("experience"):
            for exp in student["experience"][:1]:
                parts.append(f"Experience: {exp.get('role', '')} at {exp.get('company', '')}")
        
        # Career objective
        if student.get("career_objective"):
            parts.append(f"Objective: {student['career_objective']}")
        
        # Location preference
        if student.get("preferred_locations"):
            parts.append(f"Preferred locations: {', '.join(student['preferred_locations'][:3])}")
        
        # Category
        if student.get("primary_category"):
            parts.append(f"Domain: {student['primary_category']}")
        
        return " | ".join(parts)
    
    def internship_to_text(self, internship: Dict) -> str:
        """Convert internship to text"""
        parts = []
        
        # Title and company
        parts.append(f"{internship.get('title', 'Internship')} at {internship.get('company', internship.get('organisation_name', 'Company'))}")
        
        # Skills
        if internship.get("skills"):
            parts.append(f"Required skills: {', '.join(internship['skills'])}")
        
        # Location
        location = internship.get("location") or f"{internship.get('city', '')}, {internship.get('state', '')}"
        if location:
            parts.append(f"Location: {location}")
        
        # Stipend
        if internship.get("stipend"):
            parts.append(f"Stipend: ₹{internship['stipend']:,}/month")
        
        # Duration
        if internship.get("duration") or internship.get("duration_months"):
            duration = internship.get("duration") or f"{internship.get('duration_months')} months"
            parts.append(f"Duration: {duration}")
        
        # Category/Sector
        sector = internship.get("sector") or internship.get("category")
        if sector:
            parts.append(f"Sector: {sector}")
        
        # Description (truncated)
        if internship.get("description"):
            desc = internship["description"][:200]
            parts.append(f"Description: {desc}")
        
        return " | ".join(parts)
    
    def create_training_pairs(
        self,
        config: FineTuningConfig
    ) -> Tuple[List[InputExample], List[InputExample]]:
        """Create training pairs for contrastive learning"""
        
        logger.info("Creating training pairs...")
        
        positive_pairs = []
        all_pairs = []
        
        # Group matches by quality
        excellent_matches = [m for m in self.matches if m["match_quality"] == "excellent"]
        good_matches = [m for m in self.matches if m["match_quality"] == "good"]
        moderate_matches = [m for m in self.matches if m["match_quality"] == "moderate"]
        poor_matches = [m for m in self.matches if m["match_quality"] == "poor"]
        
        logger.info(f"Match distribution: Excellent={len(excellent_matches)}, Good={len(good_matches)}, "
                   f"Moderate={len(moderate_matches)}, Poor={len(poor_matches)}")
        
        # Create positive pairs (excellent and good matches)
        for match in excellent_matches + good_matches:
            student = self.student_lookup.get(match["student_id"])
            internship = self.internship_lookup.get(match["internship_id"])
            
            if student and internship:
                student_text = self.student_to_text(student)
                internship_text = self.internship_to_text(internship)
                
                # Higher score for excellent matches
                label = 1.0 if match["match_quality"] == "excellent" else 0.8
                
                positive_pairs.append(InputExample(
                    texts=[student_text, internship_text],
                    label=label
                ))
        
        # Create negative pairs (poor matches and random non-matches)
        negative_pairs = []
        
        # Use poor matches as hard negatives
        for match in poor_matches[:len(positive_pairs) // 2]:
            student = self.student_lookup.get(match["student_id"])
            internship = self.internship_lookup.get(match["internship_id"])
            
            if student and internship:
                student_text = self.student_to_text(student)
                internship_text = self.internship_to_text(internship)
                
                negative_pairs.append(InputExample(
                    texts=[student_text, internship_text],
                    label=0.0
                ))
        
        # Add random negatives
        student_ids = list(self.student_lookup.keys())
        internship_ids = list(self.internship_lookup.keys())
        
        existing_pairs = {(m["student_id"], m["internship_id"]) for m in self.matches}
        
        while len(negative_pairs) < len(positive_pairs):
            sid = random.choice(student_ids)
            iid = random.choice(internship_ids)
            
            if (sid, iid) not in existing_pairs:
                student = self.student_lookup[sid]
                internship = self.internship_lookup[iid]
                
                student_text = self.student_to_text(student)
                internship_text = self.internship_to_text(internship)
                
                negative_pairs.append(InputExample(
                    texts=[student_text, internship_text],
                    label=0.0
                ))
                existing_pairs.add((sid, iid))
        
        all_pairs = positive_pairs + negative_pairs
        random.shuffle(all_pairs)
        
        # Split into train and validation
        split_idx = int(len(all_pairs) * config.train_split)
        train_pairs = all_pairs[:split_idx]
        val_pairs = all_pairs[split_idx:]
        
        logger.info(f"Created {len(train_pairs)} training pairs, {len(val_pairs)} validation pairs")
        
        return train_pairs, val_pairs
    
    def create_triplets(self, config: FineTuningConfig) -> List[InputExample]:
        """Create triplets for triplet loss (anchor, positive, negative)"""
        
        logger.info("Creating training triplets...")
        triplets = []
        
        # Group matches by student
        student_matches = defaultdict(list)
        for match in self.matches:
            student_matches[match["student_id"]].append(match)
        
        for student_id, matches in tqdm(student_matches.items(), desc="Creating triplets"):
            student = self.student_lookup.get(student_id)
            if not student:
                continue
            
            anchor_text = self.student_to_text(student)
            
            # Sort matches by score
            sorted_matches = sorted(matches, key=lambda x: x["match_score"], reverse=True)
            
            # Positive: high score matches
            positives = [m for m in sorted_matches if m["match_score"] >= 0.6]
            # Negatives: low score matches
            negatives = [m for m in sorted_matches if m["match_score"] < 0.4]
            
            for pos_match in positives[:5]:
                pos_internship = self.internship_lookup.get(pos_match["internship_id"])
                if not pos_internship:
                    continue
                
                positive_text = self.internship_to_text(pos_internship)
                
                # Get hard negatives
                hard_negs = negatives[:config.num_hard_negatives] if negatives else []
                
                # Add random negatives if not enough hard negatives
                while len(hard_negs) < config.num_hard_negatives:
                    random_internship = random.choice(self.internships)
                    if random_internship["id"] != pos_match["internship_id"]:
                        hard_negs.append({"internship_id": random_internship["id"]})
                
                for neg_match in hard_negs:
                    neg_internship = self.internship_lookup.get(neg_match["internship_id"])
                    if not neg_internship:
                        continue
                    
                    negative_text = self.internship_to_text(neg_internship)
                    
                    triplets.append(InputExample(
                        texts=[anchor_text, positive_text, negative_text]
                    ))
        
        random.shuffle(triplets)
        logger.info(f"Created {len(triplets)} triplets")
        
        return triplets


class MultipleNegativesRankingDataset:
    """Create dataset for Multiple Negatives Ranking Loss"""
    
    def __init__(self, matching_dataset: MatchingDataset):
        self.matching_dataset = matching_dataset
    
    def create_examples(self) -> List[InputExample]:
        """Create examples: (query, positive) pairs"""
        examples = []
        
        # Group by student for efficient batch creation
        student_positives = defaultdict(list)
        
        for match in self.matching_dataset.matches:
            if match["match_score"] >= 0.6:  # Only use good matches
                student_positives[match["student_id"]].append(match["internship_id"])
        
        for student_id, internship_ids in tqdm(student_positives.items(), desc="Creating MNR examples"):
            student = self.matching_dataset.student_lookup.get(student_id)
            if not student:
                continue
            
            query_text = self.matching_dataset.student_to_text(student)
            
            for iid in internship_ids[:3]:  # Limit per student
                internship = self.matching_dataset.internship_lookup.get(iid)
                if internship:
                    positive_text = self.matching_dataset.internship_to_text(internship)
                    examples.append(InputExample(texts=[query_text, positive_text]))
        
        logger.info(f"Created {len(examples)} MNR examples")
        return examples


class EmbeddingFineTuner:
    """Fine-tune sentence transformer for matching"""
    
    def __init__(self, config: FineTuningConfig):
        self.config = config
        self.model = None
        self.dataset = None
        
    def load_base_model(self):
        """Load base sentence transformer model"""
        logger.info(f"Loading base model: {self.config.base_model}")
        self.model = SentenceTransformer(self.config.base_model, device=self.config.device)
        self.model.max_seq_length = self.config.max_seq_length
        logger.info(f"Model loaded with dimension: {self.model.get_sentence_embedding_dimension()}")
    
    def load_data(self):
        """Load training data"""
        self.dataset = MatchingDataset(DATA_DIR)
        self.dataset.load()
    
    def train_with_contrastive_loss(self):
        """Train using contrastive loss"""
        logger.info("Training with Contrastive Loss...")
        
        train_pairs, val_pairs = self.dataset.create_training_pairs(self.config)
        
        train_dataloader = DataLoader(
            train_pairs,
            shuffle=True,
            batch_size=self.config.batch_size
        )
        
        # Contrastive loss
        train_loss = losses.ContrastiveLoss(model=self.model)
        
        # Evaluator
        evaluator = evaluation.BinaryClassificationEvaluator.from_input_examples(
            val_pairs,
            batch_size=self.config.batch_size,
            name="val"
        )
        
        # Training
        warmup_steps = int(len(train_dataloader) * self.config.epochs * 0.1)
        
        self.model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            evaluator=evaluator,
            epochs=self.config.epochs,
            warmup_steps=warmup_steps,
            optimizer_params={'lr': self.config.learning_rate},
            weight_decay=self.config.weight_decay,
            evaluation_steps=self.config.evaluation_steps,
            output_path=str(FINE_TUNED_DIR / self.config.output_model_name),
            save_best_model=True,
            show_progress_bar=True
        )
    
    def train_with_cosine_loss(self):
        """Train using cosine similarity loss"""
        logger.info("Training with Cosine Similarity Loss...")
        
        train_pairs, val_pairs = self.dataset.create_training_pairs(self.config)
        
        train_dataloader = DataLoader(
            train_pairs,
            shuffle=True,
            batch_size=self.config.batch_size
        )
        
        train_loss = losses.CosineSimilarityLoss(model=self.model)
        
        evaluator = evaluation.EmbeddingSimilarityEvaluator.from_input_examples(
            val_pairs,
            batch_size=self.config.batch_size,
            name="val"
        )
        
        self.model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            evaluator=evaluator,
            epochs=self.config.epochs,
            warmup_steps=self.config.warmup_steps,
            optimizer_params={'lr': self.config.learning_rate},
            weight_decay=self.config.weight_decay,
            evaluation_steps=self.config.evaluation_steps,
            output_path=str(FINE_TUNED_DIR / self.config.output_model_name),
            save_best_model=True,
            show_progress_bar=True
        )
    
    def train_with_mnrl(self):
        """Train using Multiple Negatives Ranking Loss (MNRL)"""
        logger.info("Training with Multiple Negatives Ranking Loss...")
        
        mnr_dataset = MultipleNegativesRankingDataset(self.dataset)
        examples = mnr_dataset.create_examples()
        
        # Split
        split_idx = int(len(examples) * self.config.train_split)
        train_examples = examples[:split_idx]
        val_examples = examples[split_idx:]
        
        train_dataloader = DataLoader(
            train_examples,
            shuffle=True,
            batch_size=self.config.batch_size
        )
        
        # MNRL - in-batch negatives make training efficient
        train_loss = losses.MultipleNegativesRankingLoss(model=self.model)
        
        # Create evaluation pairs
        eval_pairs = []
        for ex in val_examples[:500]:
            eval_pairs.append(InputExample(texts=ex.texts, label=1.0))
            
            # Add negative
            random_ex = random.choice(examples)
            if random_ex.texts[1] != ex.texts[1]:
                eval_pairs.append(InputExample(
                    texts=[ex.texts[0], random_ex.texts[1]],
                    label=0.0
                ))
        
        evaluator = evaluation.EmbeddingSimilarityEvaluator.from_input_examples(
            eval_pairs,
            batch_size=self.config.batch_size,
            name="val"
        )
        
        self.model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            evaluator=evaluator,
            epochs=self.config.epochs,
            warmup_steps=self.config.warmup_steps,
            optimizer_params={'lr': self.config.learning_rate},
            weight_decay=self.config.weight_decay,
            evaluation_steps=self.config.evaluation_steps,
            output_path=str(FINE_TUNED_DIR / self.config.output_model_name),
            save_best_model=True,
            show_progress_bar=True
        )
    
    def train(self):
        """Main training method"""
        self.load_base_model()
        self.load_data()
        
        if self.config.loss_type == "contrastive":
            self.train_with_contrastive_loss()
        elif self.config.loss_type == "cosine":
            self.train_with_cosine_loss()
        elif self.config.loss_type == "multiple_negatives":
            self.train_with_mnrl()
        else:
            raise ValueError(f"Unknown loss type: {self.config.loss_type}")
        
        # Save config
        config_path = FINE_TUNED_DIR / self.config.output_model_name / "training_config.json"
        with open(config_path, 'w') as f:
            json.dump({
                "base_model": self.config.base_model,
                "loss_type": self.config.loss_type,
                "epochs": self.config.epochs,
                "batch_size": self.config.batch_size,
                "learning_rate": self.config.learning_rate,
                "trained_at": datetime.now().isoformat(),
                "num_students": len(self.dataset.students),
                "num_internships": len(self.dataset.internships),
                "num_matches": len(self.dataset.matches)
            }, f, indent=2)
        
        logger.info(f"✅ Model saved to: {FINE_TUNED_DIR / self.config.output_model_name}")
    
    def evaluate(self):
        """Evaluate the fine-tuned model"""
        logger.info("Evaluating fine-tuned model...")
        
        # Load fine-tuned model
        model_path = FINE_TUNED_DIR / self.config.output_model_name
        if not model_path.exists():
            logger.error(f"Model not found at {model_path}")
            return
        
        fine_tuned_model = SentenceTransformer(str(model_path))
        base_model = SentenceTransformer(self.config.base_model)
        
        # Load test data
        test_dir = DATA_DIR / "test"
        with open(test_dir / "students.json") as f:
            test_students = json.load(f)
        with open(test_dir / "internships.json") as f:
            test_internships = json.load(f)
        with open(test_dir / "matches.json") as f:
            test_matches = json.load(f)
        
        # Create test texts
        student_lookup = {s["id"]: s for s in test_students}
        internship_lookup = {i["id"]: i for i in test_internships}
        
        results = {"base_model": [], "fine_tuned": []}
        
        for match in tqdm(test_matches[:500], desc="Evaluating"):
            student = student_lookup.get(match["student_id"])
            internship = internship_lookup.get(match["internship_id"])
            
            if not student or not internship:
                continue
            
            student_text = self.dataset.student_to_text(student)
            internship_text = self.dataset.internship_to_text(internship)
            
            # Base model similarity
            base_emb_s = base_model.encode(student_text)
            base_emb_i = base_model.encode(internship_text)
            base_sim = np.dot(base_emb_s, base_emb_i) / (np.linalg.norm(base_emb_s) * np.linalg.norm(base_emb_i))
            
            # Fine-tuned model similarity
            ft_emb_s = fine_tuned_model.encode(student_text)
            ft_emb_i = fine_tuned_model.encode(internship_text)
            ft_sim = np.dot(ft_emb_s, ft_emb_i) / (np.linalg.norm(ft_emb_s) * np.linalg.norm(ft_emb_i))
            
            ground_truth = match["match_score"]
            
            results["base_model"].append({
                "predicted": float(base_sim),
                "ground_truth": ground_truth,
                "error": abs(float(base_sim) - ground_truth)
            })
            results["fine_tuned"].append({
                "predicted": float(ft_sim),
                "ground_truth": ground_truth,
                "error": abs(float(ft_sim) - ground_truth)
            })
        
        # Calculate metrics
        base_mae = np.mean([r["error"] for r in results["base_model"]])
        ft_mae = np.mean([r["error"] for r in results["fine_tuned"]])
        
        base_corr = np.corrcoef(
            [r["predicted"] for r in results["base_model"]],
            [r["ground_truth"] for r in results["base_model"]]
        )[0, 1]
        
        ft_corr = np.corrcoef(
            [r["predicted"] for r in results["fine_tuned"]],
            [r["ground_truth"] for r in results["fine_tuned"]]
        )[0, 1]
        
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        print(f"\nBase Model ({self.config.base_model}):")
        print(f"  Mean Absolute Error: {base_mae:.4f}")
        print(f"  Correlation with Ground Truth: {base_corr:.4f}")
        
        print(f"\nFine-tuned Model ({self.config.output_model_name}):")
        print(f"  Mean Absolute Error: {ft_mae:.4f}")
        print(f"  Correlation with Ground Truth: {ft_corr:.4f}")
        
        improvement = ((base_mae - ft_mae) / base_mae) * 100
        print(f"\n📈 Improvement: {improvement:.1f}% reduction in MAE")
        
        # Save evaluation results
        eval_results = {
            "base_model": {
                "name": self.config.base_model,
                "mae": float(base_mae),
                "correlation": float(base_corr)
            },
            "fine_tuned_model": {
                "name": self.config.output_model_name,
                "mae": float(ft_mae),
                "correlation": float(ft_corr)
            },
            "improvement_pct": float(improvement),
            "evaluated_at": datetime.now().isoformat(),
            "num_test_samples": len(results["base_model"])
        }
        
        eval_path = FINE_TUNED_DIR / self.config.output_model_name / "evaluation_results.json"
        with open(eval_path, 'w') as f:
            json.dump(eval_results, f, indent=2)
        
        return eval_results


def main():
    """Main training function"""
    
    print("=" * 70)
    print("🧠 YUVA SETU - EMBEDDING FINE-TUNING")
    print("=" * 70)
    
    # Configuration
    config = FineTuningConfig(
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        output_model_name="yuvasetu-embeddings-v1",
        epochs=3,
        batch_size=32,
        learning_rate=2e-5,
        loss_type="multiple_negatives",  # Best for retrieval tasks
        use_hard_negatives=True
    )
    
    print(f"\n📋 Configuration:")
    print(f"  Base Model: {config.base_model}")
    print(f"  Loss Type: {config.loss_type}")
    print(f"  Epochs: {config.epochs}")
    print(f"  Batch Size: {config.batch_size}")
    print(f"  Device: {config.device}")
    
    try:
        trainer = EmbeddingFineTuner(config)
        
        # Train
        print("\n🏋️ Starting fine-tuning...")
        trainer.train()
        
        # Evaluate
        print("\n📊 Evaluating model...")
        trainer.evaluate()
        
        print("\n" + "=" * 70)
        print("🎉 FINE-TUNING COMPLETE!")
        print(f"Model saved to: {FINE_TUNED_DIR / config.output_model_name}")
        print("=" * 70)
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nRun data generation first:")
        print("  python app/scripts/data/generate_synthetic_dataset.py")


if __name__ == "__main__":
    main()