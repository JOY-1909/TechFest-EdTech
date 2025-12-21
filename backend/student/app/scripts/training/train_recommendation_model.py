# File: app/scripts/training/train_recommendation_model.py
"""
Complete training pipeline for Yuva Setu Recommendation Engine
Includes weight optimization and model evaluation
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import logging
from datetime import datetime
from scipy.optimize import minimize, differential_evolution
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error, mean_absolute_error
from tqdm import tqdm
import warnings

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
MODEL_DIR = PROJECT_ROOT / "models"
FINE_TUNED_DIR = MODEL_DIR / "fine_tuned"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

print(f"Project root: {PROJECT_ROOT}")
print(f"Data directory: {DATA_DIR}")
print(f"Model directory: {MODEL_DIR}")


@dataclass
class TrainingConfig:
    """Training configuration"""
    # Model settings
    base_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    use_fine_tuned: bool = True
    fine_tuned_model: str = "yuvasetu-embeddings-v1"
    embedding_dim: int = 384
    
    # Weight optimization
    cv_folds: int = 5
    optimization_method: str = "differential_evolution"  # SLSQP, differential_evolution
    
    # Initial weights
    initial_weights: Dict[str, float] = field(default_factory=lambda: {
        "skills": 0.40,
        "location": 0.20,
        "stipend": 0.20,
        "timeline": 0.10,
        "category": 0.10
    })
    
    # Weight bounds
    weight_bounds: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "skills": (0.2, 0.6),
        "location": (0.1, 0.3),
        "stipend": (0.1, 0.3),
        "timeline": (0.05, 0.2),
        "category": (0.05, 0.2)
    })


class RecommendationWeightTrainer:
    """Train optimal weights for recommendation scoring"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.model = None
        self.students = []
        self.internships = []
        self.ground_truth = []
        self.student_embeddings = {}
        self.internship_embeddings = {}
        self.student_lookup = {}
        self.internship_lookup = {}
        
    def load_data(self):
        """Load training data"""
        logger.info("Loading training data...")
        
        train_dir = DATA_DIR / "train"
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
            self.ground_truth = json.load(f)
        
        self.student_lookup = {s["id"]: s for s in self.students}
        self.internship_lookup = {i["id"]: i for i in self.internships}
        
        logger.info(f"Loaded: {len(self.students)} students, {len(self.internships)} internships, {len(self.ground_truth)} matches")
    
    def load_model(self):
        """Load embedding model"""
        from sentence_transformers import SentenceTransformer
        
        # Check for fine-tuned model
        fine_tuned_path = FINE_TUNED_DIR / self.config.fine_tuned_model
        
        if self.config.use_fine_tuned and fine_tuned_path.exists():
            logger.info(f"Loading fine-tuned model: {fine_tuned_path}")
            self.model = SentenceTransformer(str(fine_tuned_path))
        else:
            logger.info(f"Loading base model: {self.config.base_model}")
            self.model = SentenceTransformer(self.config.base_model)
    
    def precompute_embeddings(self):
        """Precompute embeddings for all students and internships"""
        logger.info("Precomputing embeddings...")
        
        # Student embeddings
        for student in tqdm(self.students, desc="Student embeddings"):
            text = self._student_to_text(student)
            self.student_embeddings[student["id"]] = self.model.encode(text, convert_to_numpy=True)
        
        # Internship embeddings
        for internship in tqdm(self.internships, desc="Internship embeddings"):
            text = self._internship_to_text(internship)
            self.internship_embeddings[internship["id"]] = self.model.encode(text, convert_to_numpy=True)
        
        logger.info(f"Computed {len(self.student_embeddings)} student embeddings, {len(self.internship_embeddings)} internship embeddings")
    
    def _student_to_text(self, student: Dict) -> str:
        """Convert student to embedding text"""
        parts = []
        
        if student.get("skills"):
            skill_names = [s["name"] if isinstance(s, dict) else s for s in student["skills"]]
            parts.append(" ".join(skill_names))
        
        if student.get("career_objective"):
            parts.append(student["career_objective"])
        
        if student.get("education"):
            for edu in student["education"][:1]:
                parts.append(f"{edu.get('field_of_study', '')} {edu.get('institution', '')}")
        
        if student.get("primary_category"):
            parts.append(student["primary_category"])
        
        return " ".join(parts)
    
    def _internship_to_text(self, internship: Dict) -> str:
        """Convert internship to embedding text"""
        parts = []
        
        if internship.get("title"):
            parts.append(internship["title"])
        
        if internship.get("skills"):
            parts.append(" ".join(internship["skills"]))
        
        if internship.get("description"):
            parts.append(internship["description"][:200])
        
        sector = internship.get("sector") or internship.get("category")
        if sector:
            parts.append(sector)
        
        return " ".join(parts)
    
    def compute_dimension_scores(self, student: Dict, internship: Dict) -> Dict[str, float]:
        """Compute individual dimension scores"""
        scores = {}
        
        # 1. Skill similarity (embedding-based)
        student_emb = self.student_embeddings.get(student["id"])
        internship_emb = self.internship_embeddings.get(internship["id"])
        
        if student_emb is not None and internship_emb is not None:
            norm_s = np.linalg.norm(student_emb)
            norm_i = np.linalg.norm(internship_emb)
            if norm_s > 0 and norm_i > 0:
                scores["skills"] = max(0, float(np.dot(student_emb, internship_emb) / (norm_s * norm_i)))
            else:
                scores["skills"] = 0.0
        else:
            scores["skills"] = 0.0
        
        # 2. Location score
        work_type = internship.get("work_type", "")
        student_city = student.get("city", "")
        internship_city = internship.get("city", "")
        preferred_locations = student.get("preferred_locations", [])
        
        if work_type in ["Remote", "Hybrid"]:
            scores["location"] = 1.0
        elif student_city and student_city == internship_city:
            scores["location"] = 1.0
        elif internship_city in preferred_locations:
            scores["location"] = 0.85
        elif student.get("state") == internship.get("state"):
            scores["location"] = 0.6
        else:
            scores["location"] = 0.3
        
        # 3. Stipend score
        stipend = internship.get("stipend", 0)
        min_stipend = student.get("preferred_stipend_min", 0)
        max_stipend = student.get("preferred_stipend_max", 100000)
        
        if min_stipend <= stipend <= max_stipend:
            scores["stipend"] = 1.0
        elif stipend > max_stipend:
            scores["stipend"] = 0.8  # Higher than expected is still good
        elif stipend >= min_stipend * 0.7:
            scores["stipend"] = 0.5
        else:
            scores["stipend"] = 0.2
        
        # 4. Timeline/Duration score
        duration = internship.get("duration_months", 3)
        preferred_durations = student.get("preferred_duration_months", [3])
        
        if duration in preferred_durations:
            scores["timeline"] = 1.0
        elif any(abs(duration - pd) <= 1 for pd in preferred_durations):
            scores["timeline"] = 0.7
        else:
            scores["timeline"] = 0.4
        
        # 5. Category/Domain match
        student_category = student.get("primary_category", "").lower()
        internship_sector = (internship.get("sector") or internship.get("category", "")).lower()
        
        if student_category and internship_sector:
            if student_category == internship_sector:
                scores["category"] = 1.0
            elif student_category in internship_sector or internship_sector in student_category:
                scores["category"] = 0.7
            else:
                scores["category"] = 0.3
        else:
            scores["category"] = 0.5
        
        return scores
    
    def compute_weighted_score(self, dimension_scores: Dict[str, float], weights: Dict[str, float]) -> float:
        """Compute final weighted score"""
        total = 0.0
        for dim, score in dimension_scores.items():
            if dim in weights:
                total += score * weights[dim]
        return total
    
    def prepare_training_pairs(self) -> List[Tuple[Dict, Dict, float]]:
        """Prepare (student, internship, ground_truth_score) pairs"""
        pairs = []
        
        for match in self.ground_truth:
            student = self.student_lookup.get(match["student_id"])
            internship = self.internship_lookup.get(match["internship_id"])
            
            if student and internship:
                pairs.append((student, internship, match["match_score"]))
        
        logger.info(f"Prepared {len(pairs)} training pairs")
        return pairs
    
    def compute_loss(self, weights_array: np.ndarray, pairs: List[Tuple]) -> float:
        """Compute MSE loss for given weights"""
        weight_names = ["skills", "location", "stipend", "timeline", "category"]
        weights = {name: weights_array[i] for i, name in enumerate(weight_names)}
        
        total_loss = 0.0
        for student, internship, gt_score in pairs:
            dim_scores = self.compute_dimension_scores(student, internship)
            predicted = self.compute_weighted_score(dim_scores, weights)
            total_loss += (predicted - gt_score) ** 2
        
        return total_loss / len(pairs)
    
    def optimize_weights_slsqp(self, pairs: List[Tuple]) -> Dict[str, float]:
        """Optimize weights using SLSQP"""
        logger.info("Optimizing weights with SLSQP...")
        
        weight_names = ["skills", "location", "stipend", "timeline", "category"]
        x0 = np.array([self.config.initial_weights[name] for name in weight_names])
        
        # Constraint: weights sum to 1
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}]
        
        # Bounds for each weight
        bounds = [self.config.weight_bounds[name] for name in weight_names]
        
        result = minimize(
            self.compute_loss,
            x0,
            args=(pairs,),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        weights = {name: float(result.x[i]) for i, name in enumerate(weight_names)}
        logger.info(f"Optimized weights: {weights}, Loss: {result.fun:.6f}")
        
        return weights
    
    def optimize_weights_de(self, pairs: List[Tuple]) -> Dict[str, float]:
        """Optimize weights using Differential Evolution"""
        logger.info("Optimizing weights with Differential Evolution...")
        
        weight_names = ["skills", "location", "stipend", "timeline", "category"]
        bounds = [self.config.weight_bounds[name] for name in weight_names]
        
        def loss_with_normalization(x):
            # Normalize to sum to 1
            x_norm = x / np.sum(x)
            return self.compute_loss(x_norm, pairs)
        
        result = differential_evolution(
            loss_with_normalization,
            bounds,
            maxiter=500,
            seed=42,
            workers=-1,
            updating='deferred',
            polish=True
        )
        
        # Normalize final result
        final_weights = result.x / np.sum(result.x)
        weights = {name: float(final_weights[i]) for i, name in enumerate(weight_names)}
        
        logger.info(f"Optimized weights: {weights}, Loss: {result.fun:.6f}")
        return weights
    
    def cross_validate(self, pairs: List[Tuple], n_folds: int = 5) -> Dict[str, Any]:
        """Perform k-fold cross-validation"""
        logger.info(f"Running {n_folds}-fold cross-validation...")
        
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        pairs_array = np.array(pairs, dtype=object)
        
        fold_results = []
        all_weights = []
        
        for fold, (train_idx, val_idx) in enumerate(kf.split(pairs_array)):
            logger.info(f"Fold {fold + 1}/{n_folds}")
            
            train_pairs = [pairs[i] for i in train_idx]
            val_pairs = [pairs[i] for i in val_idx]
            
            # Optimize on training fold
            if self.config.optimization_method == "differential_evolution":
                weights = self.optimize_weights_de(train_pairs)
            else:
                weights = self.optimize_weights_slsqp(train_pairs)
            
            all_weights.append(weights)
            
            # Evaluate on validation fold
            weight_names = ["skills", "location", "stipend", "timeline", "category"]
            weights_array = np.array([weights[name] for name in weight_names])
            val_loss = self.compute_loss(weights_array, val_pairs)
            
            # Calculate additional metrics
            predictions = []
            ground_truths = []
            for student, internship, gt_score in val_pairs:
                dim_scores = self.compute_dimension_scores(student, internship)
                pred = self.compute_weighted_score(dim_scores, weights)
                predictions.append(pred)
                ground_truths.append(gt_score)
            
            mae = mean_absolute_error(ground_truths, predictions)
            rmse = np.sqrt(mean_squared_error(ground_truths, predictions))
            correlation = np.corrcoef(predictions, ground_truths)[0, 1]
            
            fold_results.append({
                "fold": fold + 1,
                "weights": weights,
                "val_loss": float(val_loss),
                "mae": float(mae),
                "rmse": float(rmse),
                "correlation": float(correlation)
            })
            
            logger.info(f"  Val Loss: {val_loss:.6f}, MAE: {mae:.4f}, Correlation: {correlation:.4f}")
        
        # Average weights across folds
        avg_weights = {}
        for name in ["skills", "location", "stipend", "timeline", "category"]:
            avg_weights[name] = np.mean([w[name] for w in all_weights])
        
        # Normalize
        total = sum(avg_weights.values())
        avg_weights = {k: v/total for k, v in avg_weights.items()}
        
        return {
            "fold_results": fold_results,
            "average_weights": avg_weights,
            "average_val_loss": np.mean([r["val_loss"] for r in fold_results]),
            "std_val_loss": np.std([r["val_loss"] for r in fold_results]),
            "average_mae": np.mean([r["mae"] for r in fold_results]),
            "average_correlation": np.mean([r["correlation"] for r in fold_results])
        }
    
    def train(self) -> Dict[str, Any]:
        """Main training method"""
        logger.info("=" * 60)
        logger.info("STARTING WEIGHT TRAINING PIPELINE")
        logger.info("=" * 60)
        
        # Load data and model
        self.load_data()
        self.load_model()
        self.precompute_embeddings()
        
        # Prepare pairs
        pairs = self.prepare_training_pairs()
        
        if len(pairs) < 50:
            raise ValueError(f"Not enough training pairs: {len(pairs)}")
        
        # Cross-validation
        cv_results = self.cross_validate(
            pairs, 
            n_folds=min(self.config.cv_folds, len(pairs) // 20)
        )
        
        # Final optimization on all data
        logger.info("\nFinal optimization on all data...")
        if self.config.optimization_method == "differential_evolution":
            final_weights = self.optimize_weights_de(pairs)
        else:
            final_weights = self.optimize_weights_slsqp(pairs)
        
        # Compile results
        results = {
            "config": {
                "base_model": self.config.base_model,
                "use_fine_tuned": self.config.use_fine_tuned,
                "fine_tuned_model": self.config.fine_tuned_model if self.config.use_fine_tuned else None,
                "optimization_method": self.config.optimization_method,
                "cv_folds": self.config.cv_folds
            },
            "cross_validation": {
                "average_weights": cv_results["average_weights"],
                "average_val_loss": float(cv_results["average_val_loss"]),
                "std_val_loss": float(cv_results["std_val_loss"]),
                "average_mae": float(cv_results["average_mae"]),
                "average_correlation": float(cv_results["average_correlation"]),
                "fold_details": cv_results["fold_results"]
            },
            "final_weights": final_weights,
            "training_stats": {
                "num_students": len(self.students),
                "num_internships": len(self.internships),
                "num_pairs": len(pairs),
                "trained_at": datetime.now().isoformat()
            }
        }
        
        # Save results
        output_path = MODEL_DIR / "trained_weights.json"
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"✅ Results saved to {output_path}")
        
        return results
    
    def evaluate_on_test(self, weights: Dict[str, float]) -> Dict[str, Any]:
        """Evaluate on test set"""
        logger.info("Evaluating on test set...")
        
        test_dir = DATA_DIR / "test"
        if not test_dir.exists():
            logger.warning("Test data not found, skipping evaluation")
            return {}
        
        with open(test_dir / "students.json") as f:
            test_students = json.load(f)
        with open(test_dir / "internships.json") as f:
            test_internships = json.load(f)
        with open(test_dir / "matches.json") as f:
            test_matches = json.load(f)
        
        test_student_lookup = {s["id"]: s for s in test_students}
        test_internship_lookup = {i["id"]: i for i in test_internships}
        
        # Compute embeddings for test data
        test_student_emb = {}
        test_internship_emb = {}
        
        for student in tqdm(test_students, desc="Test student embeddings"):
            text = self._student_to_text(student)
            test_student_emb[student["id"]] = self.model.encode(text, convert_to_numpy=True)
        
        for internship in tqdm(test_internships, desc="Test internship embeddings"):
            text = self._internship_to_text(internship)
            test_internship_emb[internship["id"]] = self.model.encode(text, convert_to_numpy=True)
        
        # Temporarily swap embeddings
        orig_student_emb = self.student_embeddings
        orig_internship_emb = self.internship_embeddings
        self.student_embeddings = test_student_emb
        self.internship_embeddings = test_internship_emb
        
        predictions = []
        ground_truths = []
        quality_predictions = {"excellent": [], "good": [], "moderate": [], "poor": []}
        
        for match in test_matches:
            student = test_student_lookup.get(match["student_id"])
            internship = test_internship_lookup.get(match["internship_id"])
            
            if student and internship:
                dim_scores = self.compute_dimension_scores(student, internship)
                pred = self.compute_weighted_score(dim_scores, weights)
                predictions.append(pred)
                ground_truths.append(match["match_score"])
                
                quality = match.get("match_quality", "moderate")
                if quality in quality_predictions:
                    quality_predictions[quality].append((pred, match["match_score"]))
        
        # Restore original embeddings
        self.student_embeddings = orig_student_emb
        self.internship_embeddings = orig_internship_emb
        
        # Calculate metrics
        mae = mean_absolute_error(ground_truths, predictions)
        rmse = np.sqrt(mean_squared_error(ground_truths, predictions))
        correlation = np.corrcoef(predictions, ground_truths)[0, 1]
        
        # Quality-wise metrics
        quality_metrics = {}
        for quality, pairs in quality_predictions.items():
            if pairs:
                preds, gts = zip(*pairs)
                quality_metrics[quality] = {
                    "count": len(pairs),
                    "mae": float(mean_absolute_error(gts, preds)),
                    "avg_predicted": float(np.mean(preds)),
                    "avg_ground_truth": float(np.mean(gts))
                }
        
        return {
            "test_mae": float(mae),
            "test_rmse": float(rmse),
            "test_correlation": float(correlation),
            "num_test_samples": len(predictions),
            "quality_breakdown": quality_metrics
        }


def main():
    """Main training function"""
    print("=" * 70)
    print("🎯 YUVA SETU - RECOMMENDATION WEIGHT TRAINING")
    print("=" * 70)
    
    # Check for fine-tuned model
    fine_tuned_exists = (FINE_TUNED_DIR / "yuvasetu-embeddings-v1").exists()
    
    config = TrainingConfig(
        base_model="sentence-transformers/all-MiniLM-L6-v2",
        use_fine_tuned=fine_tuned_exists,
        fine_tuned_model="yuvasetu-embeddings-v1",
        cv_folds=5,
        optimization_method="differential_evolution"
    )
    
    print(f"\n📋 Configuration:")
    print(f"  Base Model: {config.base_model}")
    print(f"  Use Fine-tuned: {config.use_fine_tuned}")
    print(f"  Optimization: {config.optimization_method}")
    print(f"  CV Folds: {config.cv_folds}")
    
    try:
        trainer = RecommendationWeightTrainer(config)
        results = trainer.train()
        
        # Evaluate on test set
        test_results = trainer.evaluate_on_test(results["final_weights"])
        if test_results:
            results["test_evaluation"] = test_results
            
            # Update saved results
            with open(MODEL_DIR / "trained_weights.json", 'w') as f:
                json.dump(results, f, indent=2)
        
        # Print results
        print("\n" + "=" * 70)
        print("📊 TRAINING RESULTS")
        print("=" * 70)
        
        print("\n🎯 Optimized Weights:")
        for name, value in results["final_weights"].items():
            bar = "█" * int(value * 40)
            print(f"  {name:12s}: {value:.4f} {bar}")
        
        print(f"\n📈 Cross-Validation Metrics:")
        cv = results["cross_validation"]
        print(f"  Avg Val Loss: {cv['average_val_loss']:.6f} ± {cv['std_val_loss']:.6f}")
        print(f"  Avg MAE:      {cv['average_mae']:.4f}")
        print(f"  Avg Corr:     {cv['average_correlation']:.4f}")
        
        if test_results:
            print(f"\n🧪 Test Set Evaluation:")
            print(f"  Test MAE:     {test_results['test_mae']:.4f}")
            print(f"  Test RMSE:    {test_results['test_rmse']:.4f}")
            print(f"  Test Corr:    {test_results['test_correlation']:.4f}")
        
        print(f"\n✅ Model saved to: {MODEL_DIR / 'trained_weights.json'}")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("\nRun these first:")
        print("  1. python app/scripts/data/generate_synthetic_dataset.py")
        print("  2. python app/scripts/training/fine_tune_embeddings.py (optional)")


if __name__ == "__main__":
    main()